# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
"""Qwen4Exp n-gram embeddings with device and pinned-host storage."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import ClassVar

import os

from vllm import screen1b_guard as _s1b
import torch
import torch.nn.functional as F
from torch import nn

from vllm.compilation.breakable_cudagraph import eager_break_during_capture
from vllm.config import get_current_vllm_config
from vllm.distributed import get_dp_group, get_etp_group, get_tp_group
from vllm.forward_context import DPMetadata, get_forward_context
from vllm.logger import init_logger
from vllm.model_executor.layers.quantization.base_config import (
    QuantizationConfig,
    QuantizeMethodBase,
)
from vllm.model_executor.layers.quantization.compressed_tensors.compressed_tensors import (
    CompressedTensorsConfig,
    should_ignore_layer,
)
from vllm.model_executor.layers.quantization.fp8 import Fp8Config
from vllm.model_executor.layers.quantization.inc import INCConfig
from vllm.model_executor.layers.quantization.modelopt import (
    ModelOptMixedPrecisionConfig,
    ModelOptQuantConfigBase,
)
from vllm.model_executor.layers.quantization.utils.fp8_utils import (
    create_fp8_scale_parameter,
)
from vllm.model_executor.layers.quantization.utils.quant_utils import (
    is_layer_skipped,
)
from vllm.model_executor.models.utils import AutoWeightsLoader
from vllm.model_executor.parameter import (
    ModelWeightParameter,
    PerTensorScaleParameter,
)
from vllm.model_executor.utils import set_weight_attrs
from vllm.transformers_utils.configs.qwen4_exp import (
    Qwen4ExpTextConfig,
)
from vllm.triton_utils import tl, triton
from vllm.utils.platform_utils import is_uva_available
from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor

from ..common.ple import PLEVocabParallelEmbedding
from .ops.ple import ple_ngram_ids

logger = init_logger(__name__)


def _is_xpu() -> bool:
    from vllm.platforms import current_platform

    return current_platform.is_xpu()


def _ple_direct_pinned_enabled() -> bool:
    """B70 0006 gate: fill the XPU pinned PLE slabs straight from the mmap.

    Default OFF (unset or anything but "1"): the wu1ff load path runs
    unchanged. See _materialize_pinned_xpu_slabs(source=...).
    """
    return os.environ.get("B70_PLE_DIRECT_PINNED", "0") == "1"


def _host_memory_note() -> str:
    """VmRSS of this rank and node MemAvailable, for the load log line."""
    fields = {}
    for path, keys in (
        ("/proc/self/status", ("VmRSS",)),
        ("/proc/meminfo", ("MemAvailable",)),
    ):
        try:
            with open(path) as handle:
                for line in handle:
                    name, _, value = line.partition(":")
                    if name in keys:
                        fields[name] = int(value.split()[0]) / 2**20
        except OSError:
            pass
    return ", ".join(f"{k}={v:.1f} GiB" for k, v in fields.items()) or "n/a"


def _ple_fp8_enabled() -> bool:
    """B70 0007 gate: keep the XPU pinned PLE table in FP8 (E4M3).

    Default OFF (unset or anything but "1"): the table loads as today. On:
    the table comes from B70_PLE_FP8_PATH (a .safetensors file), the pinned
    slabs hold its raw FP8 bytes, and each looked-up row is dequantised
    after the gather (Qwen4ExpPLELayer._dequantize_embeddings).
    """
    return os.environ.get("B70_PLE_FP8", "0") == "1"


def _ple_int8_enabled() -> bool:
    """B70 0008 gate: keep the XPU pinned PLE table in INT8, one scale per row.

    Default OFF (unset or anything but "1"). On: the table comes from
    B70_PLE_INT8_PATH (a .safetensors file whose ``table`` is U8
    [rows, 164]: 160 int8 values then the row's float32 scale), the pinned
    slabs hold those 164-byte rows verbatim, and each looked-up row is
    dequantised after the gather as q * s. Mutually exclusive with
    B70_PLE_FP8.
    """
    return os.environ.get("B70_PLE_INT8", "0") == "1"


def _ple_int8_nvme_enabled() -> bool:
    """B70 0013 gate: serve the INT8 PLE table from NVMe (see ple_nvme.py).

    Default OFF (unset or anything but "1"): 0008 unchanged. On (requires
    B70_PLE_INT8=1): no pinned table; a per-rank pinned row cache filled by
    O_DIRECT reads of B70_PLE_INT8_NVME_PATH, resolved by a host hook before
    each real forward (model_state.b70_pre_forward).
    """
    return os.environ.get("B70_PLE_INT8_NVME", "0") == "1"


def _ple_int8_nvme_sync_only() -> bool:
    """B70 0013 diagnostic: run the hook, serve rows from the in-RAM table."""
    return os.environ.get("B70_PLE_INT8_NVME_SYNC_ONLY", "0") == "1"


# B70 0008: bytes of the per-row float32 scale packed after the int8 values.
_B70_PLE_INT8_SCALE_BYTES = 4
_B70_PLE_INT8_FORMAT = "lumnus-ple-int8-rowscale/v1"


_B70_SAFETENSORS_DTYPES = {
    "F8_E4M3": torch.float8_e4m3fn,
    "BF16": torch.bfloat16,
    "F16": torch.float16,
    "F32": torch.float32,
    "F64": torch.float64,
    "I64": torch.int64,
    "I32": torch.int32,
    "I16": torch.int16,
    "I8": torch.int8,
    "U8": torch.uint8,
    "BOOL": torch.bool,
}


def _b70_mmap_safetensors(path: str) -> dict[str, torch.Tensor]:
    """Map every tensor of a .safetensors file without reading it (B70 0007).

    Zero-copy views over one private (copy-on-write, never written) mmap, so
    rows only become resident as clean, evictable page cache when copied.
    Tensors whose dtype is outside _B70_SAFETENSORS_DTYPES are skipped (not
    mapped); callers refuse later only if a tensor they need is absent.
    Malformed offsets refuse for every tensor.
    """
    import json
    import mmap

    with open(path, "rb") as handle:
        header_len = int.from_bytes(handle.read(8), "little")
        size = os.fstat(handle.fileno()).st_size
        if header_len <= 0 or 8 + header_len > size:
            raise ValueError(f"{path}: not a safetensors file (header {header_len})")
        header = json.loads(handle.read(header_len))
        mapped = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_COPY)
    data_start = 8 + header_len
    tensors: dict[str, torch.Tensor] = {}
    for name, info in header.items():
        if name == "__metadata__":
            continue
        dtype = _B70_SAFETENSORS_DTYPES.get(info["dtype"])
        begin, end = (int(v) for v in info["data_offsets"])
        if dtype is None:
            if begin < 0 or end < begin or data_start + end > size:
                raise ValueError(f"{path}: tensor {name} offsets [{begin}, {end}) outside the file")
            continue
        shape = [int(v) for v in info["shape"]]
        numel = 1
        for dim in shape:
            numel *= dim
        itemsize = torch.empty((), dtype=dtype).element_size()
        if begin < 0 or end < begin or data_start + end > size:
            raise ValueError(f"{path}: tensor {name} offsets [{begin}, {end}) outside the file")
        if end - begin != numel * itemsize:
            raise ValueError(
                f"{path}: tensor {name} is {end - begin} bytes, shape {shape} x "
                f"{itemsize} needs {numel * itemsize}"
            )
        raw = torch.frombuffer(
            mapped, dtype=torch.uint8, count=end - begin, offset=data_start + begin
        ) if end > begin else torch.empty(0, dtype=torch.uint8)
        tensors[name] = raw.view(dtype).reshape(shape)
    return tensors


def _b70_copy_rows(
    destination: torch.Tensor,
    segments: list[tuple[int, torch.Tensor]],
    first_row: int,
) -> int:
    """Fill ``destination`` with table rows [first_row, first_row + len) (0007).

    ``segments`` are (global start row, rows) pieces of one logical table;
    same-dtype pieces are copied as raw bytes (no numeric conversion, also
    for FP8). Rows no segment covers are zeroed (0x00 = +0.0 in E4M3).
    Returns the number of rows copied from the segments.
    """
    count = destination.shape[0]
    covered = torch.zeros(count, dtype=torch.bool)
    copied = 0
    for seg_start, seg in segments:
        lo = max(first_row, seg_start)
        hi = min(first_row + count, seg_start + seg.shape[0])
        if lo >= hi:
            continue
        src = seg.narrow(0, lo - seg_start, hi - lo)
        dst = destination.narrow(0, lo - first_row, hi - lo)
        if src.dtype == dst.dtype and src.element_size() == 1:
            dst.view(torch.uint8).copy_(src.view(torch.uint8))
        else:
            dst.copy_(src)
        covered[lo - first_row : hi - first_row] = True
        copied += hi - lo
    if not bool(covered.all()):
        destination.view(torch.uint8)[~covered] = 0
    return copied


def _b70_fp8_lut(scale: torch.Tensor) -> torch.Tensor:
    """256-entry float32 table: E4M3 code -> value * scale (0007).

    Every E4M3 value (3 mantissa bits) times a BF16/F32 scale (<= 24 bits)
    is exact in float32, so rounding lut[code] to BF16 once equals the stock
    ``embeddings.to(bf16) * scale.to(bf16)`` bit for bit.
    """
    codes = torch.arange(256, dtype=torch.int32).to(torch.uint8)
    values = codes.view(torch.float8_e4m3fn).to(torch.float32)
    return values * scale.detach().to(device="cpu", dtype=torch.float32).reshape(())


def _b70_fp8_dequantize_lut(
    lut: torch.Tensor, embeddings: torch.Tensor, output_dtype: torch.dtype
) -> torch.Tensor:
    """Dequantise gathered FP8 PLE rows with the code LUT (0007)."""
    codes = embeddings.view(torch.uint8)
    values = torch.index_select(lut, 0, codes.reshape(-1).to(torch.int64))
    return values.reshape(codes.shape).to(output_dtype)


def _b70_ple_fp8_segments(
    tensors: dict[str, torch.Tensor],
    org_vocab_size: int,
    embedding_dim: int,
    split_ngram_parts: int,
) -> tuple[list[tuple[int, torch.Tensor]], torch.Tensor, str]:
    """Resolve the FP8 PLE rows and global scale in a mapped file (0007).

    Accepted layouts (the file written by the table-extraction step):
      * ``table`` [>= org_vocab_size, dim] F8_E4M3 + ``weight_scale``;
      * the checkpoint's own keys, any prefix: ``...shard_<i>.weight``
        (i < split_ngram_parts, ceil(org_vocab_size / parts) rows each, the
        last one shorter) + ``...weight_scale``.
    The scale must be one element (the FP8 checkpoint's single global
    scale). Anything else refuses to start.
    """
    scale_keys = [k for k in tensors if k == "weight_scale" or k.endswith(".weight_scale")]
    if len(scale_keys) != 1:
        raise ValueError(
            f"FP8 PLE file must hold exactly one weight_scale, found {scale_keys}"
        )
    scale = tensors[scale_keys[0]]
    if scale.numel() != 1:
        raise ValueError(
            f"FP8 PLE scale {scale_keys[0]} has shape {tuple(scale.shape)}; "
            "only one global scale is supported"
        )
    scale = scale.reshape(1).to(torch.float32)
    if not bool(torch.isfinite(scale).all()) or float(scale[0]) <= 0.0:
        raise ValueError(f"FP8 PLE scale must be finite and > 0, got {float(scale[0])}")

    def check(name: str, tensor: torch.Tensor, rows: int | None) -> None:
        if tensor.dtype != torch.float8_e4m3fn:
            raise ValueError(f"FP8 PLE tensor {name} is {tensor.dtype}, expected float8_e4m3fn")
        if tensor.ndim != 2 or tensor.shape[1] != embedding_dim:
            raise ValueError(
                f"FP8 PLE tensor {name} has shape {tuple(tensor.shape)}, "
                f"expected [*, {embedding_dim}]"
            )
        if rows is not None and tensor.shape[0] != rows:
            raise ValueError(
                f"FP8 PLE tensor {name} has {tensor.shape[0]} rows, expected {rows}"
            )

    if "table" in tensors:
        table = tensors["table"]
        check("table", table, None)
        if table.shape[0] < org_vocab_size:
            raise ValueError(
                f"FP8 PLE table has {table.shape[0]} rows, expected >= {org_vocab_size}"
            )
        return [(0, table)], scale, f"table {tuple(table.shape)}"

    import re

    shard_re = re.compile(r"(?:^|\.)shard_(\d+)\.weight$")
    shards: dict[int, str] = {}
    for name in tensors:
        match = shard_re.search(name)
        if match:
            index = int(match.group(1))
            if index in shards:
                raise ValueError(f"FP8 PLE shard {index} appears twice ({shards[index]}, {name})")
            shards[index] = name
    shard_size = (org_vocab_size + split_ngram_parts - 1) // split_ngram_parts
    expected = [
        i for i in range(split_ngram_parts)
        if min(shard_size, org_vocab_size - i * shard_size) > 0
    ]
    if sorted(shards) != expected:
        raise ValueError(
            f"FP8 PLE file needs 'table' or shards {expected[0]}..{expected[-1]} "
            f"(split_ngram_parts={split_ngram_parts}); found {len(shards)} shard keys"
        )
    segments = []
    for index in expected:
        start = index * shard_size
        rows = min(shard_size, org_vocab_size - start)
        check(shards[index], tensors[shards[index]], rows)
        segments.append((start, tensors[shards[index]]))
    return segments, scale, f"{len(segments)} shards x {shard_size} rows"


def _b70_ple_fp8_layout_check(
    tensors: dict[str, torch.Tensor], buffers: dict[str, torch.Tensor]
) -> list[str]:
    """Compare the file's optional n-gram layout tensors with the model (0007).

    For each of ngram_heads_offsets / ngram_heads_vocab_sizes /
    layer_multipliers present in the file (any prefix), the values must equal
    the model's loaded buffer, else the table rows index a different hash
    layout. Absent ones are skipped. Returns the names that were compared.
    """
    compared = []
    for leaf, buffer in buffers.items():
        keys = [k for k in tensors if k == leaf or k.endswith("." + leaf)]
        if not keys:
            continue
        if len(keys) != 1:
            raise ValueError(f"FP8 PLE file has {len(keys)} '{leaf}' tensors: {keys}")
        got = tensors[keys[0]]
        want = buffer.detach().to("cpu")
        if tuple(got.shape) != tuple(want.shape) or not torch.equal(
            got.to(torch.int64), want.to(torch.int64)
        ):
            raise ValueError(
                f"FP8 PLE file {leaf} {got.tolist()} does not match the model's "
                f"{want.tolist()}: the table was built for a different n-gram layout"
            )
        compared.append(leaf)
    return compared


def _b70_ple_fp8_crosscheck(
    segments: list[tuple[int, torch.Tensor]],
    scale: torch.Tensor,
    reference: torch.Tensor,
    rows: torch.Tensor,
) -> float:
    """Relative L2 error of dequantised FP8 rows against the BF16 table (0007).

    A table from the same parent weights lands near the FP8 rounding error
    (a few percent); a misaligned, wrong-scale or foreign table lands near
    or above 1.0.
    """
    picked = torch.empty(rows.numel(), reference.shape[1], dtype=torch.float8_e4m3fn)
    for out_row, row in enumerate(rows.tolist()):
        _b70_copy_rows(picked.narrow(0, out_row, 1), segments, int(row))
    lut = _b70_fp8_lut(scale)
    got = _b70_fp8_dequantize_lut(lut, picked, torch.float32)
    want = reference.index_select(0, rows).to(torch.float32)
    denom = float(torch.linalg.vector_norm(want))
    return float(torch.linalg.vector_norm(got - want)) / max(denom, 1e-30)


def _b70_safetensors_metadata(path: str) -> dict[str, str]:
    """The ``__metadata__`` block of a .safetensors header (B70 0008)."""
    import json

    with open(path, "rb") as handle:
        header_len = int.from_bytes(handle.read(8), "little")
        header = json.loads(handle.read(header_len))
    meta = header.get("__metadata__") or {}
    return {str(k): str(v) for k, v in meta.items()}


def _b70_int8_dequantize(
    packed: torch.Tensor, logical_dim: int, output_dtype: torch.dtype
) -> torch.Tensor:
    """Dequantise gathered INT8 row-scale PLE rows (B70 0008).

    ``packed`` is uint8 [..., k * (logical_dim + 4)]: per row ``logical_dim``
    int8 values then a little-endian float32 scale. Returns
    [..., k * logical_dim] in ``output_dtype``: q * s in float32, one
    rounding. Standard elementwise ops only (view, slice, cast, multiply).
    """
    storage_dim = logical_dim + _B70_PLE_INT8_SCALE_BYTES
    lead = packed.shape[:-1]
    if packed.dtype != torch.uint8 or packed.shape[-1] % storage_dim:
        raise ValueError(
            f"INT8 PLE rows must be uint8 [..., k*{storage_dim}], got "
            f"{packed.dtype} {tuple(packed.shape)}"
        )
    rows = packed.reshape(*lead, packed.shape[-1] // storage_dim, storage_dim)
    values = rows[..., :logical_dim].view(torch.int8).to(torch.float32)
    scales = rows[..., logical_dim:].contiguous().view(torch.float32)
    return (values * scales).to(output_dtype).reshape(*lead, -1)


def _b70_ple_int8_table(
    tensors: dict[str, torch.Tensor],
    org_vocab_size: int,
    embedding_dim: int,
) -> torch.Tensor:
    """Resolve the packed INT8 PLE table in a mapped file (B70 0008)."""
    if "table" not in tensors:
        raise ValueError(
            f"INT8 PLE file needs a 'table' tensor, found {sorted(tensors)[:8]}"
        )
    table = tensors["table"]
    storage_dim = embedding_dim + _B70_PLE_INT8_SCALE_BYTES
    if table.dtype != torch.uint8:
        raise ValueError(f"INT8 PLE table is {table.dtype}, expected uint8 (packed rows)")
    if table.ndim != 2 or table.shape[1] != storage_dim:
        raise ValueError(
            f"INT8 PLE table has shape {tuple(table.shape)}, expected "
            f"[*, {storage_dim}] ({embedding_dim} int8 + float32 scale)"
        )
    if table.shape[0] < org_vocab_size:
        raise ValueError(
            f"INT8 PLE table has {table.shape[0]} rows, expected >= {org_vocab_size}"
        )
    return table


def _b70_ple_int8_crosscheck(
    table: torch.Tensor,
    embedding_dim: int,
    reference: torch.Tensor,
    rows: torch.Tensor,
) -> float:
    """Relative L2 error of dequantised INT8 rows against the BF16 table (0008).

    The sampled scales must be finite and >= 0, else refuse. A table cut
    from the same BF16 rows lands near 0.0066; a shifted or foreign table
    lands near or above 1.0.
    """
    picked = table.index_select(0, rows).contiguous()
    scales = picked[:, embedding_dim:].contiguous().view(torch.float32)
    if not bool(torch.isfinite(scales).all()) or bool((scales < 0).any()):
        raise ValueError("INT8 PLE table has non-finite or negative row scales")
    got = _b70_int8_dequantize(picked, embedding_dim, torch.float32)
    want = reference.index_select(0, rows).to(torch.float32)
    denom = float(torch.linalg.vector_norm(want))
    return float(torch.linalg.vector_norm(got - want)) / max(denom, 1e-30)


def _b70_drop_page_cache(path: str) -> None:
    """Drop the file's clean page-cache pages (B70 0013 boot checks)."""
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)
    except OSError:
        pass


class _B70NvmeState:
    """Per-rank state of the B70 0013 host path (see ple_nvme.py)."""

    def __init__(self, *, server, slab, cache_view, capacity, host_ids,
                 host_ids_np, ids_dev, h2d_event, sync_only, lookahead=None) -> None:
        self.server = server
        self.lookahead = lookahead  # 0013b PleLookahead (None = off)
        self.slab = slab  # pinned uint8 [capacity, 164] (None in SYNC_ONLY)
        self.cache_view = cache_view  # its UVA view
        self.capacity = capacity
        self.host_ids = host_ids  # pinned int64 staging, slots or ids
        self.host_ids_np = host_ids_np
        self.ids_dev = ids_dev  # static device copy the gather reads
        self.h2d_event = h2d_event
        self.h2d_pending = False
        self.sync_only = sync_only


class Qwen4ExpPLEEmbedding(PLEVocabParallelEmbedding, ABC):
    """ETP-sharded PLE table shared by device and pinned-host backends."""

    supports_prefetch: ClassVar[bool] = False

    def __init__(
        self,
        num_embeddings: int,
        embedding_dim: int,
        *,
        params_dtype: torch.dtype,
        padding_size: int,
        prefix: str,
        embedding_method: "Qwen4ExpPLEEmbeddingMethod",
        num_ngram_heads: int = 1,
        max_total_tokens: int = 0,
        data_parallel_rank: int = 0,
    ) -> None:
        del num_ngram_heads, max_total_tokens
        super().__init__(
            num_embeddings,
            embedding_dim,
            params_dtype=params_dtype,
            padding_size=padding_size,
            prefix=prefix,
            quant_method=embedding_method,
            parallel_group=get_etp_group(),
        )
        self.embedding_method = embedding_method
        self.data_parallel_rank = data_parallel_rank
        tp_size = get_tp_group().world_size
        if self.tp_size % tp_size:
            raise ValueError(
                "ETP size must be divisible by TP size, but got "
                f"ETP={self.tp_size} and TP={tp_size}"
            )
        self.etp_data_parallel_size = self.tp_size // tp_size

    @abstractmethod
    def allocate_embedding_weight(
        self,
        num_embeddings: int,
        embedding_dim: int,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        """Allocate storage for the complete embedding weight."""
        raise NotImplementedError

    def dequantize(
        self,
        embeddings: torch.Tensor,
        output_dtype: torch.dtype,
    ) -> torch.Tensor:
        """Delegate storage-format conversion to the embedding method."""
        return self.embedding_method.dequantize(self, embeddings, output_dtype)

    def _get_dp_gather_slot(self, local_num_tokens: int) -> tuple[int, int]:
        """Return the per-DP slot size and this rank's slot offset."""
        if self.etp_data_parallel_size == 1:
            return local_num_tokens, 0
        dp_metadata: DPMetadata | None = get_forward_context().dp_metadata
        if dp_metadata is None:
            raise RuntimeError("ETP spanning DP requires DP token metadata")
        group_start = (self.data_parallel_rank // self.etp_data_parallel_size) * (
            self.etp_data_parallel_size
        )
        group_end = group_start + self.etp_data_parallel_size
        token_counts = dp_metadata.num_tokens_across_dp_cpu.tolist()
        group_counts = token_counts[group_start:group_end]
        slot_size = max(group_counts)
        dp_rank = get_dp_group().rank_in_group
        return slot_size, dp_rank * slot_size

    def _gather_dp_ids(
        self,
        ngram_ids: torch.Tensor,
        slot_size: int,
    ) -> torch.Tensor:
        """Gather DP-local IDs that share one ETP-sharded PLE table."""
        if self.etp_data_parallel_size == 1:
            return ngram_ids
        if ngram_ids.shape[0] < slot_size:
            padding = ngram_ids.new_zeros(
                slot_size - ngram_ids.shape[0], ngram_ids.shape[1]
            )
            ngram_ids = torch.cat((ngram_ids, padding), dim=0)
        return get_dp_group().all_gather(ngram_ids, dim=0)

    def _select_embeddings(
        self,
        embeddings: torch.Tensor,
        local_num_tokens: int,
        slot_offset: int,
    ) -> torch.Tensor:
        """Select this DP rank's rows from the ETP-reduced embeddings."""
        if self.etp_data_parallel_size == 1:
            return embeddings
        return embeddings.narrow(0, slot_offset, local_num_tokens)

    @abstractmethod
    def start_prefetch(
        self,
        hidden_states: torch.Tensor,
        ngram_ids: torch.Tensor,
    ) -> None:
        """Start an asynchronous lookup when supported."""
        raise NotImplementedError


class Qwen4ExpPLEEmbeddingMethod(QuantizeMethodBase):
    """Quantization interface shared by resident and pinned PLE tables."""

    # PLE post-load processing only validates scales in their current storage.
    requires_device_loading: bool = False

    @staticmethod
    def from_quant_config(
        quant_config: QuantizationConfig | None,
        prefix: str,
        embedding_dtype: str | None = None,
    ) -> "Qwen4ExpPLEEmbeddingMethod":
        """Select the concrete PLE embedding format for a layer."""
        if embedding_dtype == "float8_e4m3fn":
            return Qwen4ExpPLEFp8EmbeddingMethod()
        if quant_config is None:
            return Qwen4ExpPLEUnquantizedEmbeddingMethod()
        if isinstance(quant_config, ModelOptMixedPrecisionConfig):
            if quant_config._resolve_quant_algo(prefix) == "FP8":
                return Qwen4ExpPLEFp8EmbeddingMethod()
            return Qwen4ExpPLEUnquantizedEmbeddingMethod()
        if isinstance(
            quant_config, ModelOptQuantConfigBase
        ) and quant_config.is_layer_excluded(prefix):
            return Qwen4ExpPLEUnquantizedEmbeddingMethod()
        if isinstance(quant_config, CompressedTensorsConfig):
            # W4A16 pack-quantized checkpoints exclude the PLE embedding
            # through the compressed-tensors ignore list (e.g.
            # "re:.*\.ple\..*"); those tables are bf16 and load
            # unquantized. A table that is NOT excluded has no supported
            # compressed-tensors serialization here.
            if should_ignore_layer(
                prefix,
                ignore=quant_config.ignore,
                fused_mapping=quant_config.packed_modules_mapping,
            ):
                return Qwen4ExpPLEUnquantizedEmbeddingMethod()
            raise NotImplementedError(
                "Qwen4Exp PLE embedding is not in the compressed-tensors "
                "ignore list; compressed-tensors PLE quantization is not "
                "supported"
            )
        if isinstance(quant_config, INCConfig):
            # B70-0028: auto-round checkpoints (e.g. Intel/Qwen3.8-Flash-Next-
            # W4A16-AutoRound) keep the PLE table BF16 and mark it 16-bit in
            # extra_config (".*ple.*"). Resolve the layer through INC's own
            # parser; a 16-bit PLE loads unquantized. An INC-quantized table
            # has no supported serialization here.
            bits, _, _ = quant_config.get_layer_config(torch.nn.Module(), prefix)
            if bits >= 16:
                return Qwen4ExpPLEUnquantizedEmbeddingMethod()
            raise NotImplementedError(
                f"Qwen4Exp PLE embedding {prefix} is {bits}-bit in the INC "
                "extra_config; INC PLE quantization is not supported"
            )
        if not isinstance(quant_config, Fp8Config):
            raise NotImplementedError(
                "Qwen4Exp PLE embedding does not support quantization config "
                f"{type(quant_config).__name__}"
            )

        ignored_layers = quant_config.ignored_layers
        if is_layer_skipped(
            prefix,
            ignored_layers,
            quant_config.packed_modules_mapping,
            match_mode=quant_config.ignored_layers_match_mode,
        ):
            return Qwen4ExpPLEUnquantizedEmbeddingMethod()
        # PLE checkpoint shards form one runtime embedding parameter.
        shard_prefix = f"{prefix}.shard_"
        if any(name.startswith(shard_prefix) for name in ignored_layers):
            return Qwen4ExpPLEUnquantizedEmbeddingMethod()
        if not quant_config.is_checkpoint_fp8_serialized:
            raise NotImplementedError(
                "Qwen4Exp PLE embedding only supports serialized FP8 checkpoints"
            )
        return Qwen4ExpPLEFp8EmbeddingMethod()

    def apply(
        self,
        layer: nn.Module,
        x: torch.Tensor,
        bias: torch.Tensor | None = None,
    ) -> torch.Tensor:
        raise NotImplementedError("PLE weights only support embedding lookup")

    def embedding(self, layer: nn.Module, input_: torch.Tensor) -> torch.Tensor:
        if _s1b.enabled() and hasattr(layer, '_screen1b_step_device'):
            from vllm.screen1b_ple import gather_prepared
            return gather_prepared(layer, input_)
        return F.embedding(input_, layer.weight)

    @abstractmethod
    def dequantize(
        self,
        layer: nn.Module,
        embeddings: torch.Tensor,
        output_dtype: torch.dtype,
    ) -> torch.Tensor:
        """Convert looked-up PLE rows to the activation dtype."""
        raise NotImplementedError


class Qwen4ExpPLEUnquantizedEmbeddingMethod(Qwen4ExpPLEEmbeddingMethod):
    """Unquantized PLE embedding storage and lookup semantics."""

    def create_weights(
        self,
        layer: Qwen4ExpPLEEmbedding,
        input_size_per_partition: int,
        output_partition_sizes: list[int],
        input_size: int,
        output_size: int,
        params_dtype: torch.dtype,
        **extra_weight_attrs,
    ) -> None:
        del input_size, output_size
        weight = nn.Parameter(
            layer.allocate_embedding_weight(
                sum(output_partition_sizes),
                input_size_per_partition,
                params_dtype,
            ),
            requires_grad=False,
        )
        set_weight_attrs(weight, {"input_dim": 1, "output_dim": 0})
        set_weight_attrs(weight, extra_weight_attrs)
        layer.register_parameter("weight", weight)

    def dequantize(
        self,
        layer: nn.Module,
        embeddings: torch.Tensor,
        output_dtype: torch.dtype,
    ) -> torch.Tensor:
        del layer, output_dtype
        return embeddings


class Qwen4ExpPLEFp8EmbeddingMethod(Qwen4ExpPLEEmbeddingMethod):
    """FP8 PLE embedding with one global checkpoint scale."""

    def create_weights(
        self,
        layer: Qwen4ExpPLEEmbedding,
        input_size_per_partition: int,
        output_partition_sizes: list[int],
        input_size: int,
        output_size: int,
        params_dtype: torch.dtype,
        **extra_weight_attrs,
    ) -> None:
        del input_size, output_size, params_dtype
        weight_loader = extra_weight_attrs.get("weight_loader")
        weight = ModelWeightParameter(
            data=layer.allocate_embedding_weight(
                sum(output_partition_sizes),
                input_size_per_partition,
                torch.float8_e4m3fn,
            ),
            input_dim=1,
            output_dim=0,
            weight_loader=weight_loader,
        )
        layer.register_parameter("weight", weight)

        weight_scale = create_fp8_scale_parameter(
            PerTensorScaleParameter,
            output_partition_sizes,
            input_size_per_partition,
            None,
            weight_loader,
            scale_dtype=torch.float32,
        )
        layer.register_parameter("weight_scale", weight_scale)

    def process_weights_after_loading(self, layer: nn.Module) -> None:
        """Reject FP8 PLE checkpoints without a global scale."""
        sentinel = torch.finfo(torch.float32).min
        if torch.any(layer.weight_scale == sentinel):
            raise ValueError("FP8 PLE checkpoint is missing its global scale")

    def dequantize(
        self,
        layer: nn.Module,
        embeddings: torch.Tensor,
        output_dtype: torch.dtype,
    ) -> torch.Tensor:
        weight_scale = getattr(layer, "weight_scale", None)
        if weight_scale is None:
            raise RuntimeError("FP8 PLE embedding is missing its global scale")
        if weight_scale.device != embeddings.device:
            raise RuntimeError("FP8 PLE embedding scale must be on the output device")
        return embeddings.to(output_dtype) * weight_scale.to(output_dtype)


class B70PLEFp8PinnedEmbeddingMethod(Qwen4ExpPLEFp8EmbeddingMethod):
    """B70 0007: FP8 PLE held in XPU pinned slabs, LUT dequant after gather.

    Same storage and scale contract as the stock FP8 method. Dequantisation
    goes through a 256-entry code table (value x global scale, float32) so
    the XPU never has to cast float8 tensors; the result is bitwise equal to
    the stock cast-and-multiply (see _b70_fp8_lut). B70_PLE_FP8_DEQUANT=cast
    selects the stock path instead.
    """

    def process_weights_after_loading(self, layer: nn.Module) -> None:
        super().process_weights_after_loading(layer)
        scale = layer.weight_scale
        if not bool(torch.isfinite(scale).all()) or not bool((scale > 0).all()):
            raise ValueError(
                f"FP8 PLE global scale must be finite and > 0, got {scale.tolist()}"
            )
        # Read once here, not per forward (keeps env reads out of the
        # compiled graph).
        use_lut = os.environ.get("B70_PLE_FP8_DEQUANT", "lut") != "cast"
        layer._b70_ple_fp8_lut = (
            _b70_fp8_lut(scale).to(scale.device) if use_lut else None
        )

    def dequantize(
        self,
        layer: nn.Module,
        embeddings: torch.Tensor,
        output_dtype: torch.dtype,
    ) -> torch.Tensor:
        lut = getattr(layer, "_b70_ple_fp8_lut", None)
        if lut is None:
            return super().dequantize(layer, embeddings, output_dtype)
        if lut.device != embeddings.device:
            raise RuntimeError("FP8 PLE dequant table must be on the output device")
        return _b70_fp8_dequantize_lut(lut, embeddings, output_dtype)


class B70PLEInt8RowPinnedEmbeddingMethod(Qwen4ExpPLEEmbeddingMethod):
    """B70 0008: INT8 PLE with one float32 scale per row, XPU pinned slabs.

    Storage is uint8 [rows, embedding_dim + 4]: each row's int8 values then
    its scale, so the scale travels with the row through the byte gather,
    the int8 byte-sum all-reduce (one owner per row) and the copy into the
    graph-owned output. ``layer.embedding_dim`` stays the logical width
    (160); the pinned embedding reads the storage width from the weight.
    """

    def create_weights(
        self,
        layer: Qwen4ExpPLEEmbedding,
        input_size_per_partition: int,
        output_partition_sizes: list[int],
        input_size: int,
        output_size: int,
        params_dtype: torch.dtype,
        **extra_weight_attrs,
    ) -> None:
        del input_size, output_size, params_dtype
        weight = nn.Parameter(
            layer.allocate_embedding_weight(
                sum(output_partition_sizes),
                input_size_per_partition + _B70_PLE_INT8_SCALE_BYTES,
                torch.uint8,
            ),
            requires_grad=False,
        )
        set_weight_attrs(weight, {"input_dim": 1, "output_dim": 0})
        set_weight_attrs(weight, extra_weight_attrs)
        layer.register_parameter("weight", weight)

    def process_weights_after_loading(self, layer: nn.Module) -> None:
        del layer

    def dequantize(
        self,
        layer: nn.Module,
        embeddings: torch.Tensor,
        output_dtype: torch.dtype,
    ) -> torch.Tensor:
        return _b70_int8_dequantize(embeddings, layer.embedding_dim, output_dtype)


class Qwen4ExpPLEDeviceEmbedding(Qwen4ExpPLEEmbedding):
    """PLE table allocated on the active model device."""

    def allocate_embedding_weight(
        self,
        num_embeddings: int,
        embedding_dim: int,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        """Allocate the complete PLE weight on the active device."""
        if _s1b.enabled():
            if not _is_xpu() or dtype != torch.float8_e4m3fn:
                raise RuntimeError("Screen 1b mmap PLE requires native FP8 on XPU")
            # Metadata placeholder only. The publisher table is never allocated.
            # Global/TP dimensions remain in VocabParallelEmbedding metadata.
            return torch.empty((0, embedding_dim), dtype=dtype)
        return torch.empty(num_embeddings, embedding_dim, dtype=dtype)

    def start_prefetch(
        self,
        hidden_states: torch.Tensor,
        ngram_ids: torch.Tensor,
    ) -> None:
        """Resident embedding prefetch is a no-op."""
        return None

    def forward(self, ngram_ids: torch.Tensor) -> torch.Tensor:
        """Gather ETP inputs, look up embeddings, and select local rows."""
        slot_size, slot_offset = self._get_dp_gather_slot(ngram_ids.shape[0])
        gathered_ids = self._gather_dp_ids(ngram_ids, slot_size)
        embeddings = super().forward(gathered_ids)
        return self._select_embeddings(
            embeddings,
            ngram_ids.shape[0],
            slot_offset,
        )


@triton.jit
def _lookup_ple_embedding_from_pinned_kernel(
    weight_ptr,
    ids_ptr,
    output_ptr,
    embedding_dim,
    tp_vocab_start,
    tp_vocab_end,
    slab_start,
    slab_end,
    BLOCK_D: tl.constexpr,
):
    """Look up TP-owned PLE rows through an accelerator view of pinned memory.

    One launch covers one pinned slab whose rows are global ids in
    [slab_start, slab_end); rows outside the slab are not stored so a
    caller looping over slabs writes each row exactly once.
    """
    row_id = tl.program_id(0)
    global_idx = tl.load(ids_ptr + row_id)
    in_range = (global_idx >= tp_vocab_start) & (global_idx < tp_vocab_end)
    local_idx = tl.where(in_range, global_idx - tp_vocab_start, 0)
    in_slab = (global_idx >= slab_start) & (global_idx < slab_end)
    offsets = tl.arange(0, BLOCK_D)
    store_mask = (offsets < embedding_dim) & in_slab
    load_mask = (offsets < embedding_dim) & in_range
    values = tl.load(
        weight_ptr + local_idx * embedding_dim + offsets,
        mask=load_mask,
        other=0.0,
    )
    tl.store(
        output_ptr + row_id * embedding_dim + offsets,
        values,
        mask=store_mask,
    )


class Qwen4ExpPLEPinnedHostEmbedding(Qwen4ExpPLEEmbedding):
    """PLE table loaded into pinned CPU memory and looked up through UVA."""

    supports_prefetch: ClassVar[bool] = True

    def __init__(
        self,
        num_embeddings: int,
        embedding_dim: int,
        *,
        params_dtype: torch.dtype,
        padding_size: int,
        prefix: str,
        embedding_method: Qwen4ExpPLEEmbeddingMethod,
        num_ngram_heads: int = 1,
        max_total_tokens: int = 0,
        data_parallel_rank: int = 0,
    ) -> None:
        if not is_uva_available():
            raise RuntimeError("Engram CPU offload requires UVA support")
        super().__init__(
            num_embeddings,
            embedding_dim,
            params_dtype=params_dtype,
            padding_size=padding_size,
            prefix=prefix,
            embedding_method=embedding_method,
            num_ngram_heads=num_ngram_heads,
            max_total_tokens=max_total_tokens,
            data_parallel_rank=data_parallel_rank,
        )
        # B70 0008: the row width in storage can exceed the logical
        # embedding_dim (INT8 rows carry their float32 scale: 160 + 4 bytes).
        # Every storage-side size below uses it; for BF16/FP8 it is equal.
        self._b70_storage_dim = int(self.weight.shape[1])
        self._block_d = triton.next_power_of_2(self._b70_storage_dim)
        # XPU mirrors the CUDA stream API (Stream/current_stream/stream and
        # Tensor.record_stream all exist on torch 2.13.0+xpu). XPU pins at
        # most 16 GiB (2^34 B) per allocation, so a TP shard larger than
        # that cannot be one pinned tensor: the weight stays pageable here
        # and _materialize_pinned_xpu_slabs splits it after loading.
        self._xpu_slabs: list[torch.Tensor] | None = None
        self._xpu_slab_views: list[torch.Tensor] | None = None
        self._xpu_slab_rows = 0
        self._xpu_shard_rows = 0
        if _is_xpu():
            self._uva_weight = None
            self._stream_mod = torch.xpu
            self._prefetch_stream = torch.xpu.Stream()
        else:
            self._uva_weight = get_accelerator_view_from_cpu_tensor(self.weight)
            self._stream_mod = getattr(torch, self._uva_weight.device.type)
            self._prefetch_stream = self._stream_mod.Stream(
                device=self._uva_weight.device
            )
        self._prefetch_buffer = torch.empty(
            max_total_tokens * self.etp_data_parallel_size,
            num_ngram_heads,
            self._b70_storage_dim,
            dtype=self.weight.dtype,
            device=("xpu" if _is_xpu() else self._uva_weight.device),
        )
        self._output_dim = num_ngram_heads * self._b70_storage_dim
        # B70 0013: set by Qwen4ExpNGramEmbedding._b70_nvme_setup when the
        # table is served from NVMe (or SYNC_ONLY); None = 0008 unchanged.
        self._b70_nvme = None

    def allocate_embedding_weight(
        self,
        num_embeddings: int,
        embedding_dim: int,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        """Allocate the complete PLE weight in host memory.

        CUDA keeps the stock single pinned allocation. On XPU, torch
        (2.13.0+xpu) silently returns *non-pinned* memory for pinned
        requests above 2^34 bytes and the UVA-view op then faults, so the
        TP shard is allocated pageable here and re-materialized into
        <=2^34-byte pinned slabs after the rows are loaded.
        """
        if _is_xpu():
            return torch.empty(
                num_embeddings, embedding_dim, dtype=dtype, device="cpu"
            )
        return torch.empty(
            num_embeddings,
            embedding_dim,
            dtype=dtype,
            device="cpu",
            pin_memory=True,
        )

    def _materialize_pinned_xpu_slabs(
        self,
        source: torch.Tensor | list[tuple[int, torch.Tensor]] | None = None,
    ) -> None:
        """Copy the loaded shard into pinned slabs with UVA views (XPU).

        With ``source`` (the full mmap'd PLE table, B70 0006, gated by
        B70_PLE_DIRECT_PINNED=1) each slab is filled straight from the
        table's TP-owned rows, so the pageable ``self.weight`` shard is never
        written and never becomes resident: the per-rank host peak drops from
        pageable shard + pinned slabs to pinned slabs alone. Rows past the
        TP-owned range (vocab padding) are zeroed, which is what the stock
        path reads from the never-written pageable pages.

        B70 0007: ``source`` may also be a list of (global start row,
        rows) segments (a sharded FP8 file). FP8 slabs are filled as raw
        bytes and exposed to the lookup kernel as uint8 views, so no float8
        tensor reaches the XPU UVA op or Triton.
        """
        if self._xpu_slabs is not None:
            return
        shard = self.weight
        shard_rows = shard.shape[0]
        itemsize = shard.element_size()
        dim = shard.shape[1]
        # Keep every slab safely under the 2^34-byte pinned ceiling.
        slab_rows_limit = ((1 << 34) - (1 << 26)) // (dim * itemsize)
        num_slabs = max(1, -(-shard_rows // slab_rows_limit))
        slab_rows = -(-shard_rows // num_slabs)
        tp_start = self.shard_indices.org_vocab_start_index
        slabs: list[torch.Tensor] = []
        views: list[torch.Tensor] = []
        self._xpu_slab_rows = slab_rows
        self._xpu_shard_rows = shard_rows
        for index in range(num_slabs):
            start = index * slab_rows
            rows = min(slab_rows, shard_rows - start)
            if rows <= 0:
                break
            slab = torch.empty(rows, dim, dtype=shard.dtype, pin_memory=True)
            if not slab.is_pinned():
                raise RuntimeError(
                    f"PLE pinned slab {index} ({rows * dim * itemsize / 2**30:.1f}"
                    " GiB) silently failed to pin on XPU"
                )
            if source is None:
                slab.copy_(shard.narrow(0, start, rows))
            elif isinstance(source, list):
                owned = self.shard_indices.org_vocab_end_index - tp_start
                valid = max(0, min(rows, owned - start))
                if valid:
                    _b70_copy_rows(
                        slab.narrow(0, 0, valid), source, tp_start + start
                    )
                if valid < rows:
                    slab.narrow(0, valid, rows - valid).view(torch.uint8).zero_()
            else:
                owned = self.shard_indices.org_vocab_end_index - tp_start
                valid = max(0, min(rows, owned - start))
                if valid:
                    slab.narrow(0, 0, valid).copy_(
                        source.narrow(0, tp_start + start, valid)
                    )
                if valid < rows:
                    slab.narrow(0, valid, rows - valid).zero_()
            slabs.append(slab)
            if slab.dtype in (torch.float8_e4m3fn, torch.float8_e5m2):
                views.append(
                    get_accelerator_view_from_cpu_tensor(slab.view(torch.uint8))
                )
            else:
                views.append(get_accelerator_view_from_cpu_tensor(slab))
        self._xpu_slabs = slabs
        self._xpu_slab_views = views
        logger.info(
            "Materialized PLE pinned-host slabs: %d slabs x %d rows "
            "(shard %d rows, tp range [%d, %d))",
            len(slabs),
            slab_rows,
            shard_rows,
            tp_start,
            self.shard_indices.org_vocab_end_index,
        )
        # Free the transient pageable copy now that every row lives in a
        # pinned slab; the forward path only reads the slab views.
        shard.data = torch.empty(0, dim, dtype=shard.dtype)

    def _lookup(
        self,
        input_ids: torch.Tensor,
        output: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Look up local ETP rows while preserving the weight storage dtype."""
        expected_shape = (*input_ids.shape, self._b70_storage_dim)
        if output is None:
            output = torch.empty(
                expected_shape,
                dtype=self.weight.dtype,
                device=input_ids.device,
            )
        elif (
            tuple(output.shape) != expected_shape
            or output.dtype != self.weight.dtype
            or output.device != input_ids.device
        ):
            raise ValueError(
                "PLE prefetch output must match the input shape, weight dtype, "
                "and input device"
            )

        flat_ids = input_ids.reshape(-1).long()
        if flat_ids.numel():
            tp_start = self.shard_indices.org_vocab_start_index
            tp_end = self.shard_indices.org_vocab_end_index
            if self._xpu_slab_views is not None:
                # Rows owned by other ETP ranks are zero-contributions in
                # the all-reduce; no slab stores them, so zero first. Each
                # slab launch indexes rows against the slab's own bounds:
                # local_idx = id - slab_start stays inside the slab view.
                # B70 0007: FP8 slabs are exposed as uint8 views; the
                # kernel copies bytes, so the output is viewed the same way.
                kernel_output = output
                if output.dtype in (torch.float8_e4m3fn, torch.float8_e5m2):
                    kernel_output = output.view(torch.uint8)
                kernel_output.zero_()
                for index, view in enumerate(self._xpu_slab_views):
                    slab_start = tp_start + index * self._xpu_slab_rows
                    slab_end = tp_start + min(
                        (index + 1) * self._xpu_slab_rows, self._xpu_shard_rows
                    )
                    _lookup_ple_embedding_from_pinned_kernel[(flat_ids.numel(),)](
                        view,
                        flat_ids,
                        kernel_output,
                        self._b70_storage_dim,
                        slab_start,
                        slab_end,
                        slab_start,
                        slab_end,
                        BLOCK_D=self._block_d,
                    )
            elif self._uva_weight is not None:
                _lookup_ple_embedding_from_pinned_kernel[(flat_ids.numel(),)](
                    self._uva_weight,
                    flat_ids,
                    output,
                    self._b70_storage_dim,
                    tp_start,
                    tp_end,
                    tp_start,
                    tp_end,
                    BLOCK_D=self._block_d,
                )
            else:
                raise RuntimeError(
                    "XPU PLE lookup called before the pinned slabs were "
                    "materialized (PLE table not loaded?)"
                )
        return output

    def _reduce_etp_embeddings(self, embeddings: torch.Tensor) -> torch.Tensor:
        """Combine pinned lookup results owned by different ETP ranks."""
        if self.tp_size == 1:
            return embeddings
        assert self.parallel_group is not None
        if embeddings.dtype in (torch.float8_e4m3fn, torch.float8_e5m2):
            # Each vocabulary row has one owner, so reduce the raw FP8 bytes.
            reduced = self.parallel_group.all_reduce(embeddings.view(torch.int8))
            return reduced.view(embeddings.dtype)
        if embeddings.dtype == torch.uint8:
            # B70 0008: packed INT8 rows (values + scale bytes); one owner
            # per row, so the int8 byte sum is exact, as for FP8 (0007).
            reduced = self.parallel_group.all_reduce(embeddings.view(torch.int8))
            return reduced.view(torch.uint8)
        return self.parallel_group.all_reduce(embeddings)

    def _in_stream_capture(self) -> bool:
        """True while an XPU command-graph capture owns the current stream.

        L0 command-graph builds reject cross-stream event joins recorded
        into the graph ("Event dependency from handler::depends_on does not
        correspond to a node within the graph"), which kills FULL-graph
        capture at the pinned-lookup join (Stream.wait_stream on the
        prefetch stream). During capture the lookup must run directly on
        the capture stream; the pinned slabs are immutable, so replay
        re-reads them bitwise-exact through the captured kernel. Every
        non-capture path (eager prefill, PIECEWISE eager segments) keeps
        the side-stream overlap, and CUDA is unaffected.
        """
        return _is_xpu() and self._stream_mod.is_current_stream_capturing()

    @eager_break_during_capture
    def start_prefetch(
        self,
        hidden_states: torch.Tensor,
        ngram_ids: torch.Tensor,
    ) -> None:
        """Gather ETP IDs and launch their UVA lookup on the side stream."""
        slot_size, _ = self._get_dp_gather_slot(ngram_ids.shape[0])
        gathered_ids = self._gather_dp_ids(ngram_ids, slot_size)
        active_output = self._prefetch_buffer[: gathered_ids.shape[0]]
        if self._in_stream_capture():
            self._lookup(gathered_ids, output=active_output)
            return
        prefetch_stream = self._prefetch_stream
        prefetch_stream.wait_stream(self._stream_mod.current_stream())
        gathered_ids.record_stream(prefetch_stream)
        with self._stream_mod.stream(prefetch_stream):
            self._lookup(gathered_ids, output=active_output)

    @eager_break_during_capture
    def _finalize_prefetch(
        self,
        prefetch_output: torch.Tensor,
        output: torch.Tensor,
    ) -> None:
        """Join the side stream, reduce ETP shards, and select local rows."""
        if not self._in_stream_capture():
            self._stream_mod.current_stream().wait_stream(self._prefetch_stream)
        slot_size, slot_offset = self._get_dp_gather_slot(output.shape[0])
        active_output = prefetch_output[: slot_size * self.etp_data_parallel_size]
        embeddings = self._reduce_etp_embeddings(active_output)
        embeddings = self._select_embeddings(
            embeddings,
            output.shape[0],
            slot_offset,
        )
        if output.dtype in (torch.float8_e4m3fn, torch.float8_e5m2):
            # B70 0007: move FP8 rows as bytes (no float8 copy kernel).
            output.view(torch.uint8).copy_(
                embeddings.flatten(-2).view(torch.uint8)
            )
            return
        output.copy_(embeddings.flatten(-2))

    def _b70_nvme_launch(self, num_tokens_padded: int, full_graph: bool) -> None:
        """B70 0013: H2D the resolved ids and gather into _prefetch_buffer.

        Runs outside any capture, before the forward/replay. FULL batches use
        the current stream (the captured _finalize_prefetch has no join);
        PIECEWISE/eager batches use _prefetch_stream, which the eager
        _finalize_prefetch joins, so the gather overlaps layers 0-1 as today.
        NVMe mode: int64 slot ids into the pinned row cache (slot -1 = not this
        rank's row or a padding token: no load, no store, the zeroed row
        stays zero). SYNC_ONLY: host-computed global ids through the stock
        _lookup over the in-RAM slabs.
        """
        state = self._b70_nvme
        heads = self._prefetch_buffer.shape[1]
        count = num_tokens_padded * heads
        current = self._stream_mod.current_stream()
        stream = current if full_graph else self._prefetch_stream
        if stream is not current:
            stream.wait_stream(current)
        with self._stream_mod.stream(stream):
            ids = state.ids_dev[:count]
            ids.copy_(state.host_ids[:count], non_blocking=True)
            state.h2d_event.record(stream)
            state.h2d_pending = True
            output = self._prefetch_buffer[:num_tokens_padded]
            if state.sync_only:
                self._lookup(ids.view(num_tokens_padded, heads), output=output)
                return
            output.zero_()
            if count:
                _lookup_ple_embedding_from_pinned_kernel[(count,)](
                    state.cache_view,
                    ids,
                    output,
                    self._b70_storage_dim,
                    0,
                    state.capacity,
                    0,
                    state.capacity,
                    BLOCK_D=self._block_d,
                )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """Finish the pinned lookup into graph-owned output storage."""
        output = self._prefetch_buffer.new_empty(
            (hidden_states.shape[0], self._output_dim)
        )
        self._finalize_prefetch(self._prefetch_buffer, output)
        return output


class Qwen4ExpNGramEmbedding(nn.Module):
    _MASK64 = (1 << 64) - 1
    _SPLITMIX_GAMMA = 0x9E3779B97F4A7C15
    _SPLITMIX_M1 = 0xBF58476D1CE4E5B9
    _SPLITMIX_M2 = 0x94D049BB133111EB
    _PLE_LAYER_PRIME = 10007

    def _load_ple_table_from_path(self) -> bool:
        """Fill the pinned-host PLE table from the PLE_TABLE_PATH mmap file.

        XPU bring-up: this checkpoint carries no embedding rows; the full
        [org_vocab_size, head_dim] bf16 table lives in one external file
        (``{"table": Tensor}`` mmap) whose rows already follow the exact
        layout the shard branch of ``load_weights`` consumes. Slice it into
        ``split_ngram_parts`` virtual shards and run each through the same
        ``weight_loader(checkpoint_start=...)`` path so only TP-owned rows
        are copied into this rank's pinned storage.
        """
        if _is_xpu() and _ple_int8_enabled():
            return self._load_ple_int8_table()
        if _is_xpu() and _ple_fp8_enabled():
            return self._load_ple_fp8_table()
        table_path = os.environ.get("PLE_TABLE_PATH")
        if not table_path:
            return False
        embedding = self.ngram_embedding
        if not isinstance(embedding, Qwen4ExpPLEPinnedHostEmbedding):
            raise RuntimeError(
                "PLE_TABLE_PATH is set but the PLE table is device-resident; "
                "XPU requires pinned-host table storage"
            )
        table_file = torch.load(table_path, mmap=True, weights_only=True)
        table = table_file["table"] if isinstance(table_file, dict) else table_file
        org_vocab_size = embedding.org_vocab_size
        if (
            table.shape[0] < org_vocab_size
            or table.shape[1] != embedding.embedding_dim
        ):
            raise ValueError(
                f"PLE table at {table_path} has shape {tuple(table.shape)}, "
                f"expected >= [{org_vocab_size}, {embedding.embedding_dim}]"
            )
        if (
            _is_xpu()
            and _ple_direct_pinned_enabled()
            and isinstance(
                embedding.embedding_method, Qwen4ExpPLEUnquantizedEmbeddingMethod
            )
        ):
            # B70 0006: the weight_loader loop below would first fill the
            # 23.8 GiB/rank pageable shard and only then copy it into the
            # pinned slabs (47.7 GiB/rank transient, ~191 GiB over 4 ranks
            # at once). Copy the TP-owned rows from the mmap into the slabs
            # directly instead. Same rows, same dtype cast (copy_), same slab
            # layout; the pageable shard is released untouched.
            logger.info(
                "PLE direct-pinned load (B70_PLE_DIRECT_PINNED=1) starting: %s",
                _host_memory_note(),
            )
            embedding._materialize_pinned_xpu_slabs(source=table)
            logger.info(
                "Loaded PLE table from %s: direct-pinned, tp rows [%d, %d) of "
                "%d, dtype=%s, storage=pinned-host slabs; %s",
                table_path,
                embedding.shard_indices.org_vocab_start_index,
                embedding.shard_indices.org_vocab_end_index,
                org_vocab_size,
                table.dtype,
                _host_memory_note(),
            )
            return True
        shard_size = (
            org_vocab_size + self.split_ngram_parts - 1
        ) // self.split_ngram_parts
        rows_loaded = 0
        for shard_index in range(self.split_ngram_parts):
            checkpoint_start = shard_index * shard_size
            expected_rows = max(
                0, min(shard_size, org_vocab_size - checkpoint_start)
            )
            if expected_rows == 0:
                break
            shard = table.narrow(0, checkpoint_start, expected_rows)
            embedding.weight.weight_loader(
                embedding.weight,
                shard,
                checkpoint_start=checkpoint_start,
            )
            rows_loaded += expected_rows
        if _is_xpu():
            embedding._materialize_pinned_xpu_slabs()
        logger.info(
            "Loaded PLE table from %s: %d shards, %d/%d rows, dtype=%s, "
            "storage=pinned-host slabs",
            table_path,
            self.split_ngram_parts,
            rows_loaded,
            org_vocab_size,
            table.dtype,
        )
        return True

    def _load_ple_fp8_table(self) -> bool:
        """B70 0007: fill the pinned slabs with the FP8 table, raw bytes.

        Reads B70_PLE_FP8_PATH (mmap, zero-copy), refuses on any shape,
        dtype or scale mismatch, copies only this rank's TP rows into the
        FP8 pinned slabs (no pageable copy, as 0006) and sets the global
        scale. When PLE_TABLE_PATH (the BF16 table) is also set, dequantised
        FP8 rows are compared with it on a random sample and the load refuses
        above B70_PLE_FP8_MAX_REL_ERR (default 0.25).
        """
        path = os.environ["B70_PLE_FP8_PATH"]
        embedding = self.ngram_embedding
        if not isinstance(embedding, Qwen4ExpPLEPinnedHostEmbedding):
            raise RuntimeError("B70_PLE_FP8=1 requires pinned-host PLE storage")
        if not isinstance(embedding.embedding_method, Qwen4ExpPLEFp8EmbeddingMethod):
            raise RuntimeError(
                "B70_PLE_FP8=1 but the PLE embedding method is "
                f"{type(embedding.embedding_method).__name__}"
            )
        if embedding.weight.dtype != torch.float8_e4m3fn:
            raise RuntimeError(
                f"B70_PLE_FP8=1 but PLE storage dtype is {embedding.weight.dtype}"
            )
        tensors = _b70_mmap_safetensors(path)
        segments, scale, layout = _b70_ple_fp8_segments(
            tensors,
            embedding.org_vocab_size,
            embedding.embedding_dim,
            self.split_ngram_parts,
        )
        layout_checked = _b70_ple_fp8_layout_check(
            tensors,
            {
                "ngram_heads_offsets": self.ngram_heads_offsets,
                "ngram_heads_vocab_sizes": self.ngram_heads_vocab_sizes,
                "layer_multipliers": self.layer_multipliers,
            },
        )
        if layout_checked:
            layout += f"; layout matches model: {', '.join(layout_checked)}"
        reference_path = os.environ.get("PLE_TABLE_PATH")
        if reference_path and os.environ.get("B70_PLE_FP8_CROSSCHECK", "1") == "1":
            reference_file = torch.load(reference_path, mmap=True, weights_only=True)
            reference = (
                reference_file["table"]
                if isinstance(reference_file, dict)
                else reference_file
            )
            if tuple(reference.shape[1:]) != (embedding.embedding_dim,):
                raise ValueError(
                    f"BF16 PLE table {reference_path} has shape "
                    f"{tuple(reference.shape)}, cannot cross-check"
                )
            limit = min(reference.shape[0], embedding.org_vocab_size)
            generator = torch.Generator().manual_seed(20260928)
            rows = torch.randint(0, limit, (4096,), generator=generator)
            rel_err = _b70_ple_fp8_crosscheck(segments, scale, reference, rows)
            max_rel_err = float(os.environ.get("B70_PLE_FP8_MAX_REL_ERR", "0.25"))
            logger.info(
                "FP8 PLE cross-check vs %s: relative L2 error %.4f on 4096 "
                "rows (limit %.2f)",
                reference_path,
                rel_err,
                max_rel_err,
            )
            if not rel_err <= max_rel_err:
                raise ValueError(
                    f"FP8 PLE table {path} disagrees with the BF16 table "
                    f"{reference_path}: relative error {rel_err:.4f} > "
                    f"{max_rel_err} (wrong file, row order or scale?)"
                )
            del reference, reference_file
        logger.info(
            "PLE FP8 direct-pinned load (B70_PLE_FP8=1) starting: %s", _host_memory_note()
        )
        embedding._materialize_pinned_xpu_slabs(source=segments)
        with torch.no_grad():
            embedding.weight_scale.data.copy_(
                scale.to(
                    device=embedding.weight_scale.device,
                    dtype=embedding.weight_scale.dtype,
                ).reshape(embedding.weight_scale.shape)
            )
        logger.info(
            "Loaded FP8 PLE table from %s (%s): tp rows [%d, %d) of %d, "
            "scale=%g, storage=pinned-host FP8 slabs; %s",
            path,
            layout,
            embedding.shard_indices.org_vocab_start_index,
            embedding.shard_indices.org_vocab_end_index,
            embedding.org_vocab_size,
            float(scale[0]),
            _host_memory_note(),
        )
        return True

    def _load_ple_int8_table(self) -> bool:
        """B70 0008: fill the pinned slabs with the INT8 row-scale table.

        Reads B70_PLE_INT8_PATH (mmap, zero-copy), refuses on a wrong format
        tag, dtype, width, row count or n-gram layout, copies only this
        rank's TP rows (164-byte rows, verbatim) into uint8 pinned slabs (no
        pageable copy, as 0006/0007), then refuses if any owned row scale is
        non-finite or negative. When PLE_TABLE_PATH (the BF16 table) is also
        set, dequantised rows are compared with it on a random sample and the
        load refuses above B70_PLE_INT8_MAX_REL_ERR (default 0.02).
        """
        path = os.environ["B70_PLE_INT8_PATH"]
        embedding = self.ngram_embedding
        dim = embedding.embedding_dim
        if not isinstance(embedding, Qwen4ExpPLEPinnedHostEmbedding):
            raise RuntimeError("B70_PLE_INT8=1 requires pinned-host PLE storage")
        if not isinstance(
            embedding.embedding_method, B70PLEInt8RowPinnedEmbeddingMethod
        ):
            raise RuntimeError(
                "B70_PLE_INT8=1 but the PLE embedding method is "
                f"{type(embedding.embedding_method).__name__}"
            )
        if embedding.weight.dtype != torch.uint8 or (
            embedding._b70_storage_dim != dim + _B70_PLE_INT8_SCALE_BYTES
        ):
            raise RuntimeError(
                f"B70_PLE_INT8=1 but PLE storage is {embedding.weight.dtype} "
                f"width {embedding._b70_storage_dim}"
            )
        fmt = _b70_safetensors_metadata(path).get("format")
        if fmt != _B70_PLE_INT8_FORMAT:
            raise ValueError(
                f"INT8 PLE file {path} has format {fmt!r}, expected "
                f"{_B70_PLE_INT8_FORMAT!r}"
            )
        tensors = _b70_mmap_safetensors(path)
        table = _b70_ple_int8_table(tensors, embedding.org_vocab_size, dim)
        layout = f"table {tuple(table.shape)}"
        layout_checked = _b70_ple_fp8_layout_check(
            tensors,
            {
                "ngram_heads_offsets": self.ngram_heads_offsets,
                "ngram_heads_vocab_sizes": self.ngram_heads_vocab_sizes,
                "layer_multipliers": self.layer_multipliers,
            },
        )
        if layout_checked:
            layout += f"; layout matches model: {', '.join(layout_checked)}"
        nvme = _ple_int8_nvme_enabled()
        sync_only = nvme and _ple_int8_nvme_sync_only()
        if nvme and embedding.etp_data_parallel_size > 1:
            raise RuntimeError(
                "B70_PLE_INT8_NVME=1 does not support ETP spanning DP "
                f"(etp_data_parallel_size={embedding.etp_data_parallel_size})"
            )
        if nvme and not sync_only:
            # B70 0013: no pinned table; rows come from NVMe on demand.
            return self._b70_nvme_load(path, table, layout)
        reference_path = os.environ.get("PLE_TABLE_PATH")
        if reference_path and os.environ.get("B70_PLE_INT8_CROSSCHECK", "1") == "1":
            reference_file = torch.load(reference_path, mmap=True, weights_only=True)
            reference = (
                reference_file["table"]
                if isinstance(reference_file, dict)
                else reference_file
            )
            if tuple(reference.shape[1:]) != (dim,):
                raise ValueError(
                    f"BF16 PLE table {reference_path} has shape "
                    f"{tuple(reference.shape)}, cannot cross-check"
                )
            limit = min(reference.shape[0], embedding.org_vocab_size)
            generator = torch.Generator().manual_seed(20260928)
            rows = torch.randint(0, limit, (4096,), generator=generator)
            rel_err = _b70_ple_int8_crosscheck(table, dim, reference, rows)
            max_rel_err = float(os.environ.get("B70_PLE_INT8_MAX_REL_ERR", "0.02"))
            logger.info(
                "INT8 PLE cross-check vs %s: relative L2 error %.4f on 4096 "
                "rows (limit %.3f)",
                reference_path,
                rel_err,
                max_rel_err,
            )
            if not rel_err <= max_rel_err:
                raise ValueError(
                    f"INT8 PLE table {path} disagrees with the BF16 table "
                    f"{reference_path}: relative error {rel_err:.4f} > "
                    f"{max_rel_err} (wrong file, row order or packing?)"
                )
            del reference, reference_file
        logger.info(
            "PLE INT8 direct-pinned load (B70_PLE_INT8=1) starting: %s",
            _host_memory_note(),
        )
        embedding._materialize_pinned_xpu_slabs(source=[(0, table)])
        # Every owned row's scale, straight from the pinned slabs.
        step = 1 << 22
        for slab in embedding._xpu_slabs or []:
            for start in range(0, slab.shape[0], step):
                part = slab.narrow(0, start, min(step, slab.shape[0] - start))
                scales = part[:, dim:].contiguous().view(torch.float32)
                if not bool(torch.isfinite(scales).all()) or bool(
                    (scales < 0).any()
                ):
                    raise ValueError(
                        f"INT8 PLE table {path}: non-finite or negative row "
                        "scale in this rank's rows"
                    )
        logger.info(
            "Loaded INT8 PLE table from %s (%s): tp rows [%d, %d) of %d, "
            "storage=pinned-host uint8 slabs, %d B/row; %s",
            path,
            layout,
            embedding.shard_indices.org_vocab_start_index,
            embedding.shard_indices.org_vocab_end_index,
            embedding.org_vocab_size,
            embedding._b70_storage_dim,
            _host_memory_note(),
        )
        if sync_only:
            # B70 0013 diagnostic: the whole host hook, rows from RAM.
            self._b70_nvme_setup(path, table, store=None, sync_only=True)
        return True

    # ------------------------------------------------------------------
    # B70 0013: INT8 PLE table served from NVMe
    # ------------------------------------------------------------------

    def _b70_nvme_load(self, path: str, table: torch.Tensor, layout: str) -> bool:
        """Boot the NVMe path: reader checks, cache, host hook (B70 0013).

        Reads B70_PLE_INT8_NVME_PATH (default B70_PLE_INT8_PATH) in place
        with O_DIRECT; its ``table`` must have the same shape as the mapped
        0008 table. The 0008 checks are kept, through the reader: the BF16
        cross-check (when PLE_TABLE_PATH is set; the same 4,096 rows are also
        compared byte for byte with the mmap) and the row-scale check on a
        random sample of this rank's rows (B70_PLE_INT8_NVME_BOOT_SAMPLE,
        default 65,536) instead of the full-slab scan. The pageable weight
        is released; no pinned table is allocated.
        """
        from .ple_nvme import PleNvmeRowStore, safetensors_tensor_location

        embedding = self.ngram_embedding
        dim = embedding.embedding_dim
        storage = embedding._b70_storage_dim
        nvme_path = os.environ.get("B70_PLE_INT8_NVME_PATH") or path
        if nvme_path != path:
            fmt = _b70_safetensors_metadata(nvme_path).get("format")
            if fmt != _B70_PLE_INT8_FORMAT:
                raise ValueError(
                    f"B70_PLE_INT8_NVME_PATH {nvme_path} has format {fmt!r}, "
                    f"expected {_B70_PLE_INT8_FORMAT!r}"
                )
        data_start, shape, dtype = safetensors_tensor_location(nvme_path, "table")
        if dtype != "U8" or shape != list(table.shape):
            raise ValueError(
                f"B70_PLE_INT8_NVME_PATH {nvme_path}: table {dtype} {shape}, "
                f"expected U8 {list(table.shape)}"
            )
        io_threads = int(os.environ.get("B70_PLE_INT8_NVME_IO_THREADS", "16"))
        reader = os.environ.get("B70_PLE_INT8_NVME_READER", "py")
        try:
            store = PleNvmeRowStore(
                nvme_path, data_start, storage, shape[0], io_threads=io_threads,
                reader=reader,
            )
        except OSError as exc:
            raise RuntimeError(
                f"B70_PLE_INT8_NVME=1: cannot open {nvme_path} with O_DIRECT: {exc}"
            ) from exc
        logger.info(
            "PLE INT8 NVMe load (B70_PLE_INT8_NVME=1) starting: %s, data at byte "
            "%d, %d I/O threads, reader %s; %s",
            nvme_path, data_start, io_threads, reader, _host_memory_note(),
        )
        # 0008's BF16 cross-check, through the reader, plus byte equality with
        # the mmap on the same rows (tests the reader's offset math at boot).
        reference_path = os.environ.get("PLE_TABLE_PATH")
        if reference_path and os.environ.get("B70_PLE_INT8_CROSSCHECK", "1") == "1":
            reference_file = torch.load(reference_path, mmap=True, weights_only=True)
            reference = (
                reference_file["table"]
                if isinstance(reference_file, dict)
                else reference_file
            )
            if tuple(reference.shape[1:]) != (dim,):
                raise ValueError(
                    f"BF16 PLE table {reference_path} has shape "
                    f"{tuple(reference.shape)}, cannot cross-check"
                )
            limit = min(reference.shape[0], embedding.org_vocab_size)
            generator = torch.Generator().manual_seed(20260928)
            rows = torch.randint(0, limit, (4096,), generator=generator)
            picked = torch.from_numpy(store.read_rows(rows.numpy()))
            if not torch.equal(picked, table.index_select(0, rows)):
                raise ValueError(
                    f"INT8 PLE NVMe reader rows differ from the mmap of {path} "
                    "(offset math or wrong file)"
                )
            scales = picked[:, dim:].contiguous().view(torch.float32)
            if not bool(torch.isfinite(scales).all()) or bool((scales < 0).any()):
                raise ValueError("INT8 PLE table has non-finite or negative row scales")
            got = _b70_int8_dequantize(picked, dim, torch.float32)
            want = reference.index_select(0, rows).to(torch.float32)
            rel_err = float(torch.linalg.vector_norm(got - want)) / max(
                float(torch.linalg.vector_norm(want)), 1e-30
            )
            max_rel_err = float(os.environ.get("B70_PLE_INT8_MAX_REL_ERR", "0.02"))
            logger.info(
                "INT8 PLE NVMe cross-check vs %s: 4096 rows byte-equal to the "
                "mmap; relative L2 error %.4f (limit %.3f)",
                reference_path, rel_err, max_rel_err,
            )
            if not rel_err <= max_rel_err:
                raise ValueError(
                    f"INT8 PLE table {path} disagrees with the BF16 table "
                    f"{reference_path}: relative error {rel_err:.4f} > "
                    f"{max_rel_err} (wrong file, row order or packing?)"
                )
            del reference, reference_file
            _b70_drop_page_cache(path)
        # Row scales of a random sample of this rank's rows.
        tp_start = embedding.shard_indices.org_vocab_start_index
        tp_end = embedding.shard_indices.org_vocab_end_index
        sample = int(os.environ.get("B70_PLE_INT8_NVME_BOOT_SAMPLE", "65536"))
        if sample > 0 and tp_end > tp_start:
            generator = torch.Generator().manual_seed(20260929 + tp_start)
            own = torch.randint(tp_start, tp_end, (sample,), generator=generator)
            rows_np = torch.unique(own).numpy()
            picked = torch.from_numpy(store.read_rows(rows_np))
            scales = picked[:, dim:].contiguous().view(torch.float32)
            if not bool(torch.isfinite(scales).all()) or bool((scales < 0).any()):
                raise ValueError(
                    f"INT8 PLE table {nvme_path}: non-finite or negative row "
                    f"scale in this rank's sampled rows ({rows_np.shape[0]} rows)"
                )
        # No pinned table: drop the (never written) pageable shard.
        embedding.weight.data = torch.empty(0, storage, dtype=embedding.weight.dtype)
        self._b70_nvme_setup(nvme_path, table, store=store, sync_only=False)
        logger.info(
            "Serving INT8 PLE table from NVMe %s (%s): tp rows [%d, %d) of %d, "
            "%d B/row; %s",
            nvme_path, layout, tp_start, tp_end, embedding.org_vocab_size, storage,
            _host_memory_note(),
        )
        return True

    def _b70_nvme_setup(self, path: str, table: torch.Tensor, *, store,
                        sync_only: bool) -> None:
        """Cache, server and host-hash self-test for the 0013 hook."""
        from vllm.distributed import get_tp_group

        from .ple_nvme import (
            PleLookahead,
            PleNvmeRowStore,
            PleNvmeServer,
            PleNvmeStats,
            PleRowCache,
            cache_rows_per_rank,
            owned_heads,
        )

        embedding = self.ngram_embedding
        storage = embedding._b70_storage_dim
        tp_start = embedding.shard_indices.org_vocab_start_index
        tp_end = embedding.shard_indices.org_vocab_end_index
        rank = get_tp_group().rank_in_group
        max_tokens = int(embedding._prefetch_buffer.shape[0])
        heads = int(embedding._prefetch_buffer.shape[1])
        sizes = self.ngram_heads_vocab_sizes.detach().cpu().numpy()
        offsets = self.ngram_heads_offsets.detach().cpu().numpy()
        own = owned_heads(sizes, offsets, tp_start, tp_end)
        total_gib = float(os.environ.get("B70_PLE_INT8_NVME_CACHE_GIB", "8"))
        capacity = cache_rows_per_rank(total_gib, embedding.tp_size, storage)
        # Two full steps of own rows must fit (this step + the protected
        # previous one), so CLOCK can always place a step's misses.
        needed = 2 * max_tokens * max(1, own.shape[0])
        if capacity < needed:
            raise RuntimeError(
                f"B70_PLE_INT8_NVME_CACHE_GIB={total_gib} gives {capacity} rows/rank; "
                f"need >= {needed} (2 steps x {max_tokens} tokens x {own.shape[0]} "
                "own heads)"
            )
        slab = None
        cache_view = None
        if not sync_only:
            slab_bytes = capacity * storage
            if slab_bytes > (1 << 34) - (1 << 26):
                raise RuntimeError(
                    f"B70_PLE_INT8_NVME_CACHE_GIB={total_gib}: {slab_bytes / 2**30:.2f} "
                    "GiB/rank exceeds one XPU pinned allocation (2^34 B)"
                )
            slab = torch.empty(capacity, storage, dtype=torch.uint8, pin_memory=True)
            logger.info(
                "PLE NVMe pinned allocation: row cache %d x %d B = %d B "
                "(%.3f GiB), is_pinned=%s",
                capacity, storage, slab_bytes, slab_bytes / 2**30, slab.is_pinned(),
            )
            if not slab.is_pinned():
                raise RuntimeError("PLE NVMe row cache silently failed to pin")
            cache_view = get_accelerator_view_from_cpu_tensor(slab)
        cache = PleRowCache(
            tp_end - tp_start, capacity, storage,
            slab=None if slab is None else slab.numpy(),
        )
        stats = PleNvmeStats(
            rank,
            float(os.environ.get("B70_PLE_INT8_NVME_STATS_S", "60")),
            os.environ.get("B70_PLE_INT8_NVME_STATS", "0") == "1",
        )
        server = PleNvmeServer(
            tp_start=tp_start,
            tp_end=tp_end,
            multipliers=self.layer_multipliers.detach().cpu().numpy(),
            sizes=sizes,
            offsets=offsets,
            eos_token_id=self.eos_token_id,
            heads_per_ngram=self.heads_per_ngram,
            cache=cache,
            store=store,
            stats=stats,
            sync_only=sync_only,
        )
        self._b70_nvme_hash_selftest(server)
        lookahead = None
        if os.environ.get("B70_PLE_INT8_NVME_LOOKAHEAD", "0") == "1":
            if sync_only:
                logger.info("PLE NVMe lookahead ignored in SYNC_ONLY (no reads)")
            else:
                # Its own fd, bounce buffers and reader: the store is used by
                # one thread at a time. Bounded to one step of own rows.
                la_store = PleNvmeRowStore(
                    store.path, store.data_start, store.row_bytes, store.num_rows,
                    io_threads=store.io_threads, reader=store.reader,
                    queue_depth=store.queue_depth, max_batch_rows=256,
                )
                lookahead = PleLookahead(
                    server, la_store, sub_batch=256,
                    max_rows=max_tokens * max(1, own.shape[0]),
                    name=f"ple-nvme-la{rank}",
                )
                logger.info(
                    "PLE NVMe prefill lookahead on (rank %d, reader %s, <= %d rows/job)",
                    rank, store.reader, max_tokens * max(1, own.shape[0]),
                )
        device = embedding._prefetch_buffer.device
        # Dummy/profile/capture runs finalize this buffer without a hook;
        # give them zero rows instead of uninitialised bytes.
        embedding._prefetch_buffer.zero_()
        host_ids = torch.empty(max_tokens * heads, dtype=torch.int64, pin_memory=True)
        logger.info(
            "PLE NVMe pinned allocation: id staging %d B, is_pinned=%s",
            host_ids.numel() * 8, host_ids.is_pinned(),
        )
        embedding._b70_nvme = _B70NvmeState(
            server=server,
            slab=slab,
            cache_view=cache_view,
            capacity=capacity,
            host_ids=host_ids,
            host_ids_np=host_ids.numpy(),
            ids_dev=torch.empty(max_tokens * heads, dtype=torch.int64, device=device),
            h2d_event=embedding._stream_mod.Event(),
            sync_only=sync_only,
            lookahead=lookahead,
        )
        self._b70_nvme_active = True
        logger.info(
            "PLE NVMe host path ready (rank %d, %s): cache %d rows (%.2f GiB pinned, "
            "%.2f GiB maps), own heads %s, rows [%d, %d); %s",
            rank,
            "SYNC_ONLY: rows from the in-RAM table" if sync_only else "rows from NVMe",
            capacity,
            0.0 if slab is None else capacity * storage / 2**30,
            cache.meta_bytes() / 2**30,
            own.tolist(),
            tp_start,
            tp_end,
            _host_memory_note(),
        )

    def _b70_nvme_hash_selftest(self, server) -> None:
        """Host hash == device compute_ngram_ids on a padded dummy batch."""
        import numpy as np

        generator = torch.Generator().manual_seed(4242)
        lens = [1, 17, 46]
        real = sum(lens)
        padded = real + 16
        max_reqs = 8
        tokens = torch.randint(0, self.unigram_vocab_size, (padded,), generator=generator)
        tokens[torch.tensor([0, 5, 30, 31, 50])] = self.eos_token_id
        tokens = tokens.to(torch.int32)
        qsl = torch.zeros(max_reqs + 1, dtype=torch.int32)
        qsl[1 : len(lens) + 1] = torch.cumsum(torch.tensor(lens), 0).to(torch.int32)
        qsl[len(lens) + 1 :] = real
        ctx = torch.randint(
            0, self.unigram_vocab_size, (max_reqs, self.ngram_size - 1), generator=generator
        ).to(torch.int32)
        ctx[1, 0] = self.eos_token_id
        ctx[len(lens):] = self.eos_token_id
        device = self.layer_multipliers.device
        want = self.compute_ngram_ids(
            tokens.to(device), qsl.to(device), ctx.to(device)
        ).cpu().numpy()[:real]
        got = server.hash(
            tokens[:real].numpy(), qsl[: len(lens) + 1].numpy(), ctx.numpy()
        )
        if want.shape != got.shape or not np.array_equal(want, got):
            bad = int((want != got).sum()) if want.shape == got.shape else -1
            raise RuntimeError(
                f"PLE NVMe host hash differs from the device hash ({bad} ids of "
                f"{want.size}); refusing to start"
            )
        logger.info(
            "PLE NVMe host-hash self-test: %d ids equal to the device hash on %s",
            got.size, device,
        )

    def b70_nvme_pre_forward(
        self,
        tokens,
        query_start_loc,
        ngram_context,
        num_tokens_padded: int,
        full_graph: bool,
        t_start: float,
        lookahead_keys: frozenset | None = None,
    ) -> None:
        """Resolve this step's rows on the host and launch the gather (0013).

        Called by Qwen4ExpModelState.b70_pre_forward on real batches only,
        before the forward/replay. ``tokens`` are the real tokens (numpy),
        ``query_start_loc`` [num_reqs + 1] and ``ngram_context`` [num_reqs, 2]
        numpy; ``num_tokens_padded`` the forward's token count.
        """
        embedding = self.ngram_embedding
        state = embedding._b70_nvme
        if state.h2d_pending:
            # The previous step's H2D of the staging buffer must be done
            # before the host overwrites it.
            state.h2d_event.synchronize()
        prefetched = None
        wait_ms = 0.0
        if state.lookahead is not None:
            # 0013b: rows the lookahead read for this step (it is ended here
            # every step: waited for if it predicted this step's chunk,
            # cancelled otherwise).
            prefetched, wait_ms = state.lookahead.take(lookahead_keys or frozenset())
        state.server.resolve(
            tokens, query_start_loc, ngram_context, num_tokens_padded,
            state.host_ids_np, t_start=t_start, prefetched=prefetched, wait_ms=wait_ms,
        )
        embedding._b70_nvme_launch(num_tokens_padded, full_graph)

    @property
    def b70_nvme_lookahead_on(self) -> bool:
        state = getattr(self.ngram_embedding, "_b70_nvme", None)
        return state is not None and state.lookahead is not None

    def b70_nvme_lookahead_submit(self, keys, tokens, query_start_loc, ngram_context) -> None:
        """Start the 0013b lookahead for the predicted next prefill chunks."""
        self.ngram_embedding._b70_nvme.lookahead.submit(
            keys, tokens, query_start_loc, ngram_context
        )

    @classmethod
    def _splitmix64(cls, value: int) -> int:
        """Mix an integer into a deterministic unsigned 64-bit value."""
        value = (value + cls._SPLITMIX_GAMMA) & cls._MASK64
        value = ((value ^ (value >> 30)) * cls._SPLITMIX_M1) & cls._MASK64
        value = ((value ^ (value >> 27)) * cls._SPLITMIX_M2) & cls._MASK64
        return (value ^ (value >> 31)) & cls._MASK64

    @staticmethod
    def _is_prime_64(value: int) -> bool:
        """Return whether a 64-bit integer is prime."""
        if value < 2:
            return False
        for prime in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            if value % prime == 0:
                return value == prime
        exponent = value - 1
        shifts = 0
        while exponent % 2 == 0:
            exponent //= 2
            shifts += 1
        for base in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
            if base % value == 0:
                continue
            witness = pow(base, exponent, value)
            if witness in (1, value - 1):
                continue
            for _ in range(shifts - 1):
                witness = pow(witness, 2, value)
                if witness == value - 1:
                    break
            else:
                return False
        return True

    @classmethod
    def _nth_prime_after(cls, start: int, count: int) -> int:
        """Return the ``count``-th prime strictly greater than ``start``."""
        prime = int(start)
        for _ in range(count):
            candidate = prime + 1
            if candidate <= 2:
                prime = 2
                continue
            if candidate % 2 == 0:
                candidate += 1
            while not cls._is_prime_64(candidate):
                candidate += 2
            prime = candidate
        return prime

    @classmethod
    def _make_layer_multipliers(
        cls,
        *,
        ngram_size: int,
        unigram_vocab_size: int,
        seed: int,
        ple_dense_layer_id: int,
    ) -> list[int]:
        """Build deterministic hash multipliers for one PLE layer."""
        max_multiplier = ((1 << 63) - 1) // unigram_vocab_size
        half_bound = max(1, max_multiplier // 2)
        base_seed = seed + cls._PLE_LAYER_PRIME * ple_dense_layer_id
        multipliers = []
        for index in range(ngram_size):
            value = base_seed + cls._SPLITMIX_GAMMA * (index + 1)
            multipliers.append(2 * (cls._splitmix64(value) % half_bound) + 1)
        return multipliers

    @classmethod
    def _make_vocab_layout(
        cls,
        *,
        ngram_vocab_size_base: int,
        ngram_heads: int,
        ple_dense_layer_id: int,
    ) -> tuple[list[int], list[int], int]:
        """Build per-head vocabulary sizes, offsets, and total row count."""
        sizes: list[int] = []
        offsets: list[int] = []
        offset = 0
        for local_head in range(ngram_heads):
            global_head = ple_dense_layer_id * ngram_heads + local_head
            size = cls._nth_prime_after(ngram_vocab_size_base - 1, global_head + 1)
            sizes.append(size)
            offsets.append(offset)
            offset += size
        return sizes, offsets, offset

    def __init__(
        self,
        config: Qwen4ExpTextConfig,
        embedding_dim: int,
        ple_dense_layer_id: int,
        max_total_tokens: int,
        *,
        data_parallel_rank: int,
        prefix: str,
        quant_config: QuantizationConfig | None = None,
        params_dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()
        self.embedding_dim = embedding_dim
        self.ngram_size = int(config.ngram_size)
        self.heads_per_ngram = int(config.heads_per_ngram)
        self.ngram_heads = (self.ngram_size - 1) * self.heads_per_ngram
        if self.ngram_size < 2:
            raise ValueError(f"ngram_size must be >= 2, got {self.ngram_size}")
        if self.heads_per_ngram <= 0:
            raise ValueError(f"heads_per_ngram must be > 0, got {self.heads_per_ngram}")
        if embedding_dim % self.ngram_heads:
            raise ValueError(
                "ple_embed_dim must be divisible by total ngram heads: "
                f"{embedding_dim} % {self.ngram_heads} != 0"
            )
        self.head_dim = embedding_dim // self.ngram_heads
        self.eos_token_id = int(config.eos_token_id)
        self.unigram_vocab_size = int(config.vocab_size)
        self.split_ngram_parts = int(getattr(config, "split_ngram_parts", 512))
        if self.split_ngram_parts <= 0:
            raise ValueError("split_ngram_parts must be positive")

        multipliers = self._make_layer_multipliers(
            ngram_size=self.ngram_size,
            unigram_vocab_size=self.unigram_vocab_size,
            seed=int(getattr(config, "seed", 1234)),
            ple_dense_layer_id=ple_dense_layer_id,
        )
        self.register_buffer(
            "layer_multipliers",
            torch.tensor(multipliers, dtype=torch.long),
            persistent=True,
        )

        sizes, offsets, total_vocab_size = self._make_vocab_layout(
            ngram_vocab_size_base=int(config.ngram_vocab_size_base),
            ngram_heads=self.ngram_heads,
            ple_dense_layer_id=ple_dense_layer_id,
        )
        self.register_buffer(
            "ngram_heads_vocab_sizes",
            torch.tensor(sizes, dtype=torch.long),
            persistent=True,
        )
        self.register_buffer(
            "ngram_heads_offsets",
            torch.tensor(offsets, dtype=torch.long),
            persistent=True,
        )
        divisor = int(config.make_ngram_vocab_size_divisible_by)
        padded_vocab_size = ((total_vocab_size + divisor - 1) // divisor) * divisor
        embedding_prefix = f"{prefix}.ngram_embedding"
        ple_embedding_dtype = getattr(config, "ple_embedding_dtype", None)
        b70_ple_fp8 = _is_xpu() and _ple_fp8_enabled()
        if b70_ple_fp8:
            # B70 0007: the served checkpoint (W4A16, PLE excluded from
            # quantization) carries no PLE rows; the FP8 table and its global
            # scale come from B70_PLE_FP8_PATH instead of PLE_TABLE_PATH.
            if not os.environ.get("B70_PLE_FP8_PATH"):
                raise RuntimeError(
                    "B70_PLE_FP8=1 requires B70_PLE_FP8_PATH (the FP8 PLE "
                    ".safetensors file)"
                )
            ple_embedding_dtype = "float8_e4m3fn"
        b70_ple_int8 = _is_xpu() and _ple_int8_enabled()
        if b70_ple_int8:
            # B70 0008: INT8 row-scale table from B70_PLE_INT8_PATH.
            if b70_ple_fp8:
                raise RuntimeError("B70_PLE_INT8=1 and B70_PLE_FP8=1 are exclusive")
            if not os.environ.get("B70_PLE_INT8_PATH"):
                raise RuntimeError(
                    "B70_PLE_INT8=1 requires B70_PLE_INT8_PATH (the INT8 PLE "
                    ".safetensors file)"
                )
        if _is_xpu() and _ple_int8_nvme_enabled() and not b70_ple_int8:
            # B70 0013: the NVMe path serves the 0008 INT8 table only.
            raise RuntimeError("B70_PLE_INT8_NVME=1 requires B70_PLE_INT8=1")
        embedding_quant_method = Qwen4ExpPLEEmbeddingMethod.from_quant_config(
            quant_config,
            embedding_prefix,
            ple_embedding_dtype,
        )
        if b70_ple_fp8:
            embedding_quant_method = B70PLEFp8PinnedEmbeddingMethod()
        if b70_ple_int8:
            embedding_quant_method = B70PLEInt8RowPinnedEmbeddingMethod()
        if params_dtype is None:
            params_dtype = torch.get_default_dtype()
        engram_config = get_current_vllm_config().engram_config
        if engram_config is not None and engram_config.cpu_offload:
            embedding_cls = Qwen4ExpPLEPinnedHostEmbedding
        elif _is_xpu() and (
            os.environ.get("PLE_TABLE_PATH") or b70_ple_fp8 or b70_ple_int8
        ):
            # B70 XPU bring-up: pinned-host PLE table selected by
            # PLE_TABLE_PATH because the Engram route is CUDA-only
            # (config/engram.py rejects non-CUDA platforms) while the stock
            # XPU default would allocate the table device-resident (~26
            # GB/rank at TP4) and OOM the 32 GB cards.
            embedding_cls = Qwen4ExpPLEPinnedHostEmbedding
        else:
            embedding_cls = Qwen4ExpPLEDeviceEmbedding
        if _s1b.enabled() and embedding_cls is not Qwen4ExpPLEDeviceEmbedding:
            raise RuntimeError("Screen 1b forbids external/requantized/process PLE paths")
        self.ngram_embedding = embedding_cls(
            padded_vocab_size,
            self.head_dim,
            params_dtype=params_dtype,
            padding_size=divisor,
            prefix=embedding_prefix,
            embedding_method=embedding_quant_method,
            num_ngram_heads=self.ngram_heads,
            max_total_tokens=max_total_tokens,
            data_parallel_rank=data_parallel_rank,
        )
        if _s1b.enabled():
            parameter = self.ngram_embedding.weight
            parameter._vllm_offload_discard_initial_data = True
            parameter._screen1b_direct_ple = True
            parameter._vllm_is_uva_offloaded = True
            from vllm.screen1b_ple import allocate_step_buffers
            allocate_step_buffers(self.ngram_embedding, max_total_tokens, self.ngram_heads)
            _s1b.register_ple(prefix, self)
        # B70 0013: True once the NVMe (or SYNC_ONLY) host path is set up.
        self._b70_nvme_active = False
        weight = self.ngram_embedding.weight
        logger.info(
            "Initialized PLE embedding %s: quantization_method=%s, "
            "weight_dtype=%s, weight_device=%s, pinned=%s",
            embedding_prefix,
            type(embedding_quant_method).__name__,
            weight.dtype,
            weight.device,
            weight.is_pinned(),
        )

    @staticmethod
    def _shift_precompute(
        tokens: torch.Tensor, eos_token_id: int
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if tokens.dim() != 2:
            raise ValueError("tokens must be a 2D tensor")
        batch_size, seq_len = tokens.shape
        positions = torch.arange(seq_len, device=tokens.device, dtype=torch.int64)
        eos_positions = torch.where(tokens == eos_token_id, positions, -1)
        previous_eos_inclusive = torch.cummax(eos_positions, dim=1).values
        previous_eos = torch.cat(
            [
                eos_positions.new_full((batch_size, 1), -1),
                previous_eos_inclusive[:, :-1],
            ],
            dim=1,
        )
        return positions, positions.unsqueeze(0) - previous_eos - 1

    @staticmethod
    def _shift_apply(
        tokens: torch.Tensor,
        positions: torch.Tensor,
        position_in_segment: torch.Tensor,
        shift: int,
        eos_token_id: int,
    ) -> torch.Tensor:
        if shift == 0:
            return tokens
        source = positions - shift
        gather_indices = source.clamp_min(0).unsqueeze(0).expand(tokens.shape[0], -1)
        shifted = tokens.gather(1, gather_indices)
        valid = (source.unsqueeze(0) >= 0) & (position_in_segment >= shift)
        return torch.where(valid, shifted, tokens.new_full((), eos_token_id))

    def compute_ngram_ids(
        self,
        input_ids: torch.Tensor,
        query_start_loc: torch.Tensor,
        ngram_context: torch.Tensor,
        output: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Compute n-gram embedding indices for the current request layout."""
        input_ids = input_ids.reshape(-1)
        num_reqs = query_start_loc.numel() - 1
        num_tokens = input_ids.shape[0]

        if input_ids.is_cuda:
            return ple_ngram_ids(
                input_ids=input_ids,
                query_start_loc=query_start_loc,
                ngram_context=ngram_context,
                layer_multipliers=self.layer_multipliers,
                ngram_heads_vocab_sizes=self.ngram_heads_vocab_sizes,
                ngram_heads_offsets=self.ngram_heads_offsets,
                eos_token_id=self.eos_token_id,
                heads_per_ngram=self.heads_per_ngram,
                output=output,
            )
        input_ids = input_ids.long()
        query_start_loc = query_start_loc.long()
        positions = torch.arange(num_tokens, device=input_ids.device, dtype=torch.int64)
        packed = torch.full(
            (num_reqs, num_tokens),
            self.eos_token_id,
            device=input_ids.device,
            dtype=torch.int64,
        )
        request_indices = torch.searchsorted(query_start_loc, positions, right=True) - 1
        request_indices.clamp_(max=num_reqs - 1)
        columns = (positions - query_start_loc[request_indices]).clamp(
            0, packed.shape[1] - 1
        )
        packed[request_indices, columns] = input_ids
        ngram_context = ngram_context[:num_reqs].to(
            device=input_ids.device, dtype=torch.long
        )

        context = torch.cat([ngram_context, packed], dim=-1)
        positions_2d, position_in_segment = self._shift_precompute(
            context, self.eos_token_id
        )
        shifted = [context]
        for shift in range(1, self.ngram_size):
            shifted.append(
                self._shift_apply(
                    context,
                    positions_2d,
                    position_in_segment,
                    shift,
                    self.eos_token_id,
                )
            )
        adjusted_columns = columns + self.ngram_size - 1
        id_blocks = []
        for ngram in range(2, self.ngram_size + 1):
            start = (ngram - 2) * self.heads_per_ngram
            end = start + self.heads_per_ngram
            mixed = shifted[0] * self.layer_multipliers[0]
            for index in range(1, ngram):
                mixed = torch.bitwise_xor(
                    mixed, shifted[index] * self.layer_multipliers[index]
                )
            sizes = self.ngram_heads_vocab_sizes[start:end]
            offsets = self.ngram_heads_offsets[start:end]
            ids = torch.remainder(mixed.unsqueeze(-1), sizes) + offsets
            id_blocks.append(ids[request_indices, adjusted_columns])
        return torch.cat(id_blocks, dim=-1)

    def forward(
        self,
        hidden_states: torch.Tensor,
        input_ids: torch.Tensor,
        query_start_loc: torch.Tensor,
        ngram_context: torch.Tensor,
    ) -> torch.Tensor:
        embedding = self.ngram_embedding
        if embedding.supports_prefetch:
            return embedding(hidden_states)
        ngram_ids = self.compute_ngram_ids(input_ids, query_start_loc, ngram_context)
        return self.ngram_embedding(ngram_ids).flatten(-2)

    def start_prefetch(
        self,
        hidden_states: torch.Tensor,
        input_ids: torch.Tensor,
        query_start_loc: torch.Tensor,
        ngram_context: torch.Tensor,
    ) -> None:
        """Start the pinned lookup while the preceding decoder layer runs."""
        embedding = self.ngram_embedding
        if not embedding.supports_prefetch:
            return
        if self._b70_nvme_active:
            # B70 0013: ids and gather already done by the host hook before
            # the forward (b70_nvme_pre_forward); nothing to hash or launch in
            # the graph. _finalize_prefetch (in forward) is unchanged.
            return
        ngram_ids = self.compute_ngram_ids(
            input_ids,
            query_start_loc,
            ngram_context,
        )
        embedding.start_prefetch(hidden_states, ngram_ids)

    def screen1b_expected_shards(self):
        embedding = self.ngram_embedding
        size = (embedding.org_vocab_size + self.split_ngram_parts - 1) // self.split_ngram_parts
        first = embedding.shard_indices.org_vocab_start_index
        end = embedding.shard_indices.org_vocab_end_index
        return {i for i in range(self.split_ngram_parts)
                if i * size < end and min((i + 1) * size, embedding.org_vocab_size) > first}

    def begin_checkpoint_shard_coverage(self):
        if _s1b.enabled():
            self._screen1b_observed_shards = set()

    def validate_checkpoint_shard_coverage(self):
        if not _s1b.enabled():
            return
        expected = self.screen1b_expected_shards()
        if hasattr(self.ngram_embedding, '_screen1b_cache'):
            # RowStore validates every header and the full local interval;
            # the ordinary iterator skips these payloads before get_tensor.
            self._screen1b_observed_shards = expected
        observed = getattr(self, "_screen1b_observed_shards", set())
        if observed != expected:
            raise RuntimeError("PLE embedding checkpoint shard coverage is incomplete: "
                               f"missing={sorted(expected - observed)}, "
                               f"unexpected={sorted(observed - expected)}")
        _s1b.receipt("PLE_coverage_complete", shards=sorted(observed))

    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:
        """Load hash buffers and checkpoint-split embedding rows."""

        persistent_buffers = {
            "layer_multipliers": self.layer_multipliers,
            "ngram_heads_offsets": self.ngram_heads_offsets,
            "ngram_heads_vocab_sizes": self.ngram_heads_vocab_sizes,
        }
        loaded: set[str] = ({"ngram_embedding.weight"}
                            if _s1b.enabled() and hasattr(self.ngram_embedding, '_screen1b_cache')
                            else set())
        regular_weights: list[tuple[str, torch.Tensor]] = []
        shard_prefix = "ngram_embedding.shard_"

        for name, loaded_weight in weights:
            leaf_name = name.rsplit(".", 1)[-1]
            if leaf_name.startswith("hashstats_") or leaf_name == "token_lookup":
                continue
            if name in persistent_buffers:
                buffer = persistent_buffers[name]
                if buffer.shape != loaded_weight.shape:
                    raise ValueError(
                        f"Shape mismatch for {name}: expected "
                        f"{tuple(buffer.shape)}, got {tuple(loaded_weight.shape)}"
                    )
                buffer.copy_(loaded_weight.to(device=buffer.device, dtype=buffer.dtype))
                loaded.add(name)
                continue
            if name.startswith(shard_prefix) and name.endswith(".weight"):
                shard_text = name[len(shard_prefix) : -len(".weight")]
                if not shard_text.isdigit():
                    if _s1b.enabled():
                        raise ValueError(f"Malformed PLE checkpoint shard: {name}")
                    regular_weights.append((name, loaded_weight))
                    continue
                shard_index = int(shard_text)
                if shard_index >= self.split_ngram_parts:
                    raise ValueError(
                        f"PLE embedding shard index {shard_index} exceeds "
                        f"split_ngram_parts={self.split_ngram_parts}"
                    )
                if _s1b.enabled():
                    observed = self._screen1b_observed_shards
                    if shard_index in observed:
                        raise ValueError(f"Duplicate PLE embedding shard {shard_index}")
                    if shard_index not in self.screen1b_expected_shards():
                        raise ValueError(f"Unexpected nonowned PLE shard {shard_index}")
                    observed.add(shard_index)
                embedding = self.ngram_embedding
                shard_size = (
                    embedding.org_vocab_size + self.split_ngram_parts - 1
                ) // self.split_ngram_parts
                checkpoint_start = shard_index * shard_size
                expected_rows = max(
                    0,
                    min(shard_size, embedding.org_vocab_size - checkpoint_start),
                )
                expected_shape = (expected_rows, embedding.embedding_dim)
                if tuple(loaded_weight.shape) != expected_shape:
                    raise ValueError(
                        f"Shape mismatch for PLE embedding shard {shard_index}: "
                        f"expected {expected_shape}, got "
                        f"{tuple(loaded_weight.shape)}"
                    )
                if _s1b.enabled() and loaded_weight.dtype != embedding.weight.dtype:
                    raise RuntimeError("Screen 1b PLE checkpoint dtype mismatch; no requantization")
                embedding.weight.weight_loader(
                    embedding.weight,
                    loaded_weight,
                    checkpoint_start=checkpoint_start,
                )
                loaded.add("ngram_embedding.weight")
                continue
            regular_weights.append((name, loaded_weight))

        if regular_weights:
            loaded.update(AutoWeightsLoader(self).load_weights(regular_weights))
        if "ngram_embedding.weight" not in loaded:
            # XPU bring-up: the checkpoint has no embedding rows, so fill
            # the pinned-host table from the external PLE_TABLE_PATH file.
            if self._load_ple_table_from_path():
                loaded.add("ngram_embedding.weight")
                if _is_xpu() and _ple_fp8_enabled():
                    loaded.add("ngram_embedding.weight_scale")
        return loaded


__all__ = [
    "Qwen4ExpNGramEmbedding",
]

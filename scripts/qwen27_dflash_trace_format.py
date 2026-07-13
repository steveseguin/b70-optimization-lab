"""Binary format helpers for exact-Q4 native DFlash target traces."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import torch


MAGIC = b"QDFTRC1\0"
VERSION = 1
HEADER_BYTES = 256
DTYPE_BF16 = 1
FLAG_COMPLETE = 1 << 0
ROW_FLAG_PROMPT = 1 << 0
ROW_FLAG_GENERATED = 1 << 1
N_LAYERS = 5
HIDDEN_SIZE = 5120
TARGET_LAYER_IDS = (2, 17, 32, 47, 62)
HEADER = struct.Struct("<8sIIIIQIIII32s32s20s32s32s5iQ32s")
ROW_PREFIX = struct.Struct("<iiiI")
FEATURE_VALUES = N_LAYERS * HIDDEN_SIZE
FEATURE_BYTES = FEATURE_VALUES * 2
ROW_BYTES = ROW_PREFIX.size + FEATURE_BYTES

if HEADER.size != HEADER_BYTES:
    raise RuntimeError(f"trace header ABI is {HEADER.size}, expected {HEADER_BYTES}")


@dataclass(frozen=True)
class TraceHeader:
    flags: int
    request_ordinal: int
    num_prompt_tokens: int
    row_count: int
    n_layers: int
    hidden_size: int
    target_model_sha256: str
    draft_model_sha256: str
    runtime_commit: str
    runtime_dirty_patch_sha256: str
    prompt_sha256: str
    target_layer_ids: tuple[int, ...]
    payload_bytes: int


@dataclass(frozen=True)
class TraceRows:
    input_token_ids: torch.Tensor
    sampled_next_token_ids: torch.Tensor
    positions: torch.Tensor
    row_flags: torch.Tensor
    aux_hidden_states: torch.Tensor


def _hex_to_bytes(value: str, length: int, label: str) -> bytes:
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    if len(raw) != length:
        raise ValueError(f"{label} must be {length} bytes, got {len(raw)}")
    return raw


def pack_header(header: TraceHeader) -> bytes:
    if tuple(header.target_layer_ids) != TARGET_LAYER_IDS:
        raise ValueError(f"target layers must be {TARGET_LAYER_IDS}")
    return HEADER.pack(
        MAGIC,
        VERSION,
        HEADER_BYTES,
        int(header.flags),
        DTYPE_BF16,
        int(header.request_ordinal),
        int(header.num_prompt_tokens),
        int(header.row_count),
        int(header.n_layers),
        int(header.hidden_size),
        _hex_to_bytes(header.target_model_sha256, 32, "target model sha256"),
        _hex_to_bytes(header.draft_model_sha256, 32, "draft model sha256"),
        _hex_to_bytes(header.runtime_commit, 20, "runtime commit"),
        _hex_to_bytes(
            header.runtime_dirty_patch_sha256, 32, "runtime dirty patch sha256"
        ),
        _hex_to_bytes(header.prompt_sha256, 32, "prompt sha256"),
        *header.target_layer_ids,
        int(header.payload_bytes),
        bytes(32),
    )


def unpack_header(raw: bytes) -> TraceHeader:
    if len(raw) != HEADER_BYTES:
        raise ValueError(f"trace header is {len(raw)} bytes, expected {HEADER_BYTES}")
    fields = HEADER.unpack(raw)
    magic, version, header_bytes, flags, dtype = fields[:5]
    if magic != MAGIC:
        raise ValueError(f"bad trace magic: {magic!r}")
    if version != VERSION:
        raise ValueError(f"unsupported trace version: {version}")
    if header_bytes != HEADER_BYTES:
        raise ValueError(f"bad trace header size: {header_bytes}")
    if dtype != DTYPE_BF16:
        raise ValueError(f"unsupported trace feature dtype: {dtype}")
    if fields[21] != bytes(32):
        raise ValueError("trace header reserved bytes are not zero")
    target_layers = tuple(int(value) for value in fields[15:20])
    header = TraceHeader(
        flags=int(flags),
        request_ordinal=int(fields[5]),
        num_prompt_tokens=int(fields[6]),
        row_count=int(fields[7]),
        n_layers=int(fields[8]),
        hidden_size=int(fields[9]),
        target_model_sha256=fields[10].hex(),
        draft_model_sha256=fields[11].hex(),
        runtime_commit=fields[12].hex(),
        runtime_dirty_patch_sha256=fields[13].hex(),
        prompt_sha256=fields[14].hex(),
        target_layer_ids=target_layers,
        payload_bytes=int(fields[20]),
    )
    validate_header(header)
    return header


def validate_header(header: TraceHeader) -> None:
    if header.flags != FLAG_COMPLETE:
        if not (header.flags & FLAG_COMPLETE):
            raise ValueError("trace header is not marked complete")
        raise ValueError(f"trace header has unknown flag bits: {header.flags:#x}")
    if header.n_layers != N_LAYERS:
        raise ValueError(f"trace has {header.n_layers} layers, expected {N_LAYERS}")
    if header.hidden_size != HIDDEN_SIZE:
        raise ValueError(
            f"trace hidden size is {header.hidden_size}, expected {HIDDEN_SIZE}"
        )
    if header.target_layer_ids != TARGET_LAYER_IDS:
        raise ValueError(
            f"trace target layers are {header.target_layer_ids}, "
            f"expected {TARGET_LAYER_IDS}"
        )
    if header.row_count < 1:
        raise ValueError("trace contains no complete next-token rows")
    if header.num_prompt_tokens < 1:
        raise ValueError("trace num_prompt_tokens must be positive")
    if header.num_prompt_tokens > header.row_count:
        raise ValueError(
            "trace must retain the final prompt row so it can be labeled with "
            "the first generated token"
        )
    expected_payload = header.row_count * ROW_BYTES
    if header.payload_bytes != expected_payload:
        raise ValueError(
            f"trace payload is {header.payload_bytes} bytes, "
            f"expected {expected_payload}"
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_trace(path: Path) -> tuple[TraceHeader, TraceRows]:
    path = path.expanduser().resolve()
    expected_size = path.stat().st_size
    if expected_size < HEADER_BYTES:
        raise ValueError(f"trace file is truncated: {expected_size} bytes")
    with path.open("rb") as handle:
        raw_header = handle.read(HEADER_BYTES)
        header = unpack_header(raw_header)
        exact_size = HEADER_BYTES + header.payload_bytes
        if expected_size != exact_size:
            raise ValueError(
                f"trace file size is {expected_size}, expected exactly {exact_size}"
            )
        return header, _read_rows(handle, header)


def _read_rows(handle: BinaryIO, header: TraceHeader) -> TraceRows:
    input_ids = torch.empty(header.row_count, dtype=torch.int64)
    next_ids = torch.empty(header.row_count, dtype=torch.int64)
    positions = torch.empty(header.row_count, dtype=torch.int64)
    flags = torch.empty(header.row_count, dtype=torch.int64)
    features = torch.empty(
        (header.row_count, N_LAYERS, HIDDEN_SIZE), dtype=torch.bfloat16
    )
    for index in range(header.row_count):
        prefix = handle.read(ROW_PREFIX.size)
        if len(prefix) != ROW_PREFIX.size:
            raise ValueError(f"trace row {index} prefix is truncated")
        token_id, next_token_id, position, row_flags = ROW_PREFIX.unpack(prefix)
        raw_features = handle.read(FEATURE_BYTES)
        if len(raw_features) != FEATURE_BYTES:
            raise ValueError(f"trace row {index} features are truncated")
        input_ids[index] = token_id
        next_ids[index] = next_token_id
        positions[index] = position
        flags[index] = row_flags
        row = torch.frombuffer(bytearray(raw_features), dtype=torch.bfloat16)
        features[index].copy_(row.reshape(N_LAYERS, HIDDEN_SIZE))
    validate_rows(header, input_ids, next_ids, positions, flags)
    return TraceRows(input_ids, next_ids, positions, flags, features)


def validate_rows(
    header: TraceHeader,
    input_ids: torch.Tensor,
    next_ids: torch.Tensor,
    positions: torch.Tensor,
    flags: torch.Tensor,
) -> None:
    if torch.any(input_ids < 0) or torch.any(next_ids < 0):
        raise ValueError("trace contains negative token IDs")
    if int(positions[0].item()) != 0:
        raise ValueError("trace must begin at position zero (prompt reuse is forbidden)")
    if torch.any(positions[1:] != positions[:-1] + 1):
        raise ValueError("trace positions are not strictly contiguous")
    if torch.any(input_ids[1:] != next_ids[:-1]):
        raise ValueError("trace next-token labels do not align to following inputs")
    prompt_rows = flags.bitwise_and(ROW_FLAG_PROMPT).ne(0)
    generated_rows = flags.bitwise_and(ROW_FLAG_GENERATED).ne(0)
    if torch.any(flags.bitwise_and(~(ROW_FLAG_PROMPT | ROW_FLAG_GENERATED)).ne(0)):
        raise ValueError("trace row has unknown flag bits")
    if torch.any(prompt_rows & generated_rows):
        raise ValueError("trace row cannot be both prompt and generated")
    if torch.any(~(prompt_rows | generated_rows)):
        raise ValueError("trace row is missing prompt/generated classification")
    expected_prompt_rows = min(header.num_prompt_tokens, header.row_count)
    if not bool(torch.all(prompt_rows[:expected_prompt_rows])):
        raise ValueError("trace prompt row flags do not cover the prompt prefix")
    if expected_prompt_rows < header.row_count and not bool(
        torch.all(generated_rows[expected_prompt_rows:])
    ):
        raise ValueError("trace generated row flags do not cover the generated suffix")


def write_row(
    handle: BinaryIO,
    *,
    token_id: int,
    next_token_id: int,
    position: int,
    flags: int,
    features_bf16: torch.Tensor,
) -> None:
    """Test/fixture helper; production C++ writes the same ABI directly."""

    row = features_bf16.to(dtype=torch.bfloat16, device="cpu").contiguous()
    if tuple(row.shape) != (N_LAYERS, HIDDEN_SIZE):
        raise ValueError(f"bad feature row shape: {tuple(row.shape)}")
    handle.write(ROW_PREFIX.pack(token_id, next_token_id, position, flags))
    handle.write(row.view(torch.uint16).numpy().tobytes())

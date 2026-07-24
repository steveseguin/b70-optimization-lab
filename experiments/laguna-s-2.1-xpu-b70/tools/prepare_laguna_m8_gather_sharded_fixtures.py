#!/usr/bin/env python3
"""Create and independently audit CPU-only Laguna M8 gather fixture corpora.

Only the Python standard library is used.  The command has no geometry or
epoch overrides: Phase-A's production corpus is fixed.  ``_write_test_fixture``
is an internal, smaller-epoch helper for unit tests only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import os
import stat
import struct
from pathlib import Path
from typing import Any, Iterator

PRE_TIMING_EPOCHS, POST_TIMING_EPOCHS = 256, 32
EPOCHS = PRE_TIMING_EPOCHS + POST_TIMING_EPOCHS
TOKENS, TOPK, HIDDEN, RANKS = 8, 10, 3072, 4
ROOT_PREFIX = Path("/mnt/fast-ai")
FORMAT = "laguna-m8-gather-sharded-fixtures-v1"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024


def _require_root(root: Path) -> Path:
    resolved, prefix = root.expanduser().resolve(strict=False), ROOT_PREFIX.resolve(strict=True)
    if not resolved.is_relative_to(prefix):
        raise ValueError(f"fixture output must be below {prefix}: {root}")
    return resolved


def _sha_file(path: Path, offset: int = 0, length: int | None = None) -> str:
    digest = hashlib.sha256()
    with _open_regular(path) as handle:
        size = os.fstat(handle.fileno()).st_size
        if offset < 0 or offset > size:
            raise ValueError(f"invalid hash offset: {path}")
        handle.seek(offset)
        remaining = size - offset if length is None else length
        if remaining < 0 or offset + remaining > size:
            raise ValueError(f"invalid hash length: {path}")
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"short read: {path}")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def _open_regular(path: Path):
    """Open one in-root regular file without following a final symlink."""
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ValueError(f"could not open regular fixture file: {path}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"fixture path is not a regular file: {path}")
        return os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise


def _read_bounded_regular(path: Path, maximum_bytes: int) -> bytes:
    with _open_regular(path) as handle:
        size = os.fstat(handle.fileno()).st_size
        if size > maximum_bytes:
            raise ValueError(f"fixture file exceeds size bound: {path}")
        payload = handle.read(maximum_bytes + 1)
    if len(payload) != size:
        raise ValueError(f"short or unstable fixture read: {path}")
    return payload


def _write_bytes_exclusive(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _write_canonical_exclusive(path: Path, value: dict[str, Any]) -> None:
    _write_bytes_exclusive(
        path,
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )


def _masks(epochs: int) -> list[list[int]]:
    """Registered all-local, all-remote, slot-probe, then mask schedule."""
    answer: list[list[int]] = []
    for epoch in range(epochs):
        if epoch == 0:
            answer.append([0x03FF] * TOKENS)
        elif epoch == 1:
            answer.append([0] * TOKENS)
        elif epoch <= 11:
            answer.append([1 << (epoch - 2)] * TOKENS)
        else:
            start = (epoch - 12) * TOKENS
            answer.append([(start + token) & 0x03FF for token in range(TOKENS)])
    return answer


def _row_epoch(epoch: int, masks: list[int]) -> bytes:
    words = TOKENS * TOPK * HIDDEN
    blob = bytearray(words * 2)
    base = epoch * words
    for index in range(words):
        token_slot = index // HIDDEN
        token, slot = divmod(token_slot, TOPK)
        value = (base + index) & 0xFFFF if masks[token] & (1 << slot) else 0
        struct.pack_into("<H", blob, index * 2, value)
    if epoch == 0:  # protected all-local ordered-arithmetic witnesses
        # Keep every local row nonzero and finite while zero weights suppress
        # unused witness contributions.
        for row in (*range(2, 10), *range(12, 20)):
            blob[row * HIDDEN * 2 : (row + 1) * HIDDEN * 2] = b"\x80\x3f" * HIDDEN
        struct.pack_into("<H", blob, 0, 0x3F80)
        struct.pack_into("<H", blob, HIDDEN * 2, 0xBF80)
        struct.pack_into("<H", blob, (10 * HIDDEN + 1) * 2, 0x3F80)
        struct.pack_into("<H", blob, (11 * HIDDEN + 1) * 2, 0x3F80)
    return bytes(blob)


def _weights_epoch(epoch: int) -> bytes:
    blob = bytearray(TOKENS * TOPK * 4)
    for index in range(TOKENS * TOPK):
        n = epoch * TOKENS * TOPK + index
        value = (((n * 1103515245 + 12345) >> 9) & 0x007FFFFF) | 0x3F000000 | (((n >> 3) & 1) << 31)
        struct.pack_into("<I", blob, index * 4, value)
    if epoch == 0:
        blob[:] = b"\0" * len(blob)
        for index, value in ((0, 0x3F800000), (1, 0x3F800000), (10, 0x3F800000), (11, 0x3B800000)):
            struct.pack_into("<I", blob, index * 4, value)
    elif 2 <= epoch <= 11:
        blob[:] = b"\0" * len(blob)
        slot = epoch - 2
        for token in range(TOKENS):
            struct.pack_into("<I", blob, (token * TOPK + slot) * 4, 0x3F800000)
    elif epoch == 12:
        edges = (0x00000000, 0x80000000, 0x00000001, 0x80000001, 0x3F7FFFFF, 0x3F800001, 0x7F000000, 0xFF000000, 0x7F7FFFFF, 0xFF7FFFFF, 0x7F800000, 0xFF800000, 0x7FC00001, 0xFFC12345)
        for offset, value in enumerate(edges):
            struct.pack_into("<I", blob, offset * 4, value)
    return bytes(blob)


def _bf16_epoch(epoch: int, words: int, salt: int) -> bytes:
    blob = bytearray(words * 2)
    start = epoch * words
    for index in range(words):
        n = start + index
        value = (((n * 40503 + salt) & 0x007F) | 0x3F00) | (0x8000 if n % 17 == 0 else 0)
        struct.pack_into("<H", blob, index * 2, value)
    return bytes(blob)


def _write_epochs(path: Path, epochs: Iterator[bytes]) -> tuple[str, list[str]]:
    whole = hashlib.sha256()
    per_epoch: list[str] = []
    with path.open("xb") as handle:
        for blob in epochs:
            handle.write(blob)
            whole.update(blob)
            per_epoch.append(hashlib.sha256(blob).hexdigest())
        handle.flush()
        os.fsync(handle.fileno())
    return whole.hexdigest(), per_epoch


def _record(name: str, file_name: str, dtype: str, shape: list[int], hashes: tuple[str, list[str]]) -> dict[str, Any]:
    return {"name": name, "file": file_name, "dtype": dtype, "shape": shape, "sha256": hashes[0], "epoch_sha256": hashes[1]}


def _write_fixture(root: Path, epochs: int, *, test_only: bool) -> dict[str, Any]:
    root = _require_root(root)
    if root.exists():
        raise FileExistsError(f"refusing to overwrite fixture root: {root}")
    root.mkdir(parents=True)
    masks = _masks(epochs)
    specs = {
        "route_rows": ("route_rows.uint16.le.bin", "<u2", [epochs, 80, HIDDEN], (_row_epoch(epoch, masks[epoch]) for epoch in range(epochs))),
        "weights": ("weights.uint32.le.bin", "<u4", [epochs, TOKENS, TOPK], (_weights_epoch(epoch) for epoch in range(epochs))),
        "scale_add_input": ("scale_add_input.uint16.le.bin", "<u2", [epochs, TOKENS, HIDDEN], (_bf16_epoch(epoch, TOKENS * HIDDEN, 0x11) for epoch in range(epochs))),
        "four_rank_tail": ("four_rank_tail.uint16.le.bin", "<u2", [epochs, RANKS - 1, TOKENS, HIDDEN], (_bf16_epoch(epoch, (RANKS - 1) * TOKENS * HIDDEN, 0x22) for epoch in range(epochs))),
        "residual_input": ("residual_input.uint16.le.bin", "<u2", [epochs, TOKENS, HIDDEN], (_bf16_epoch(epoch, TOKENS * HIDDEN, 0x33) for epoch in range(epochs))),
        "norm_weight": ("norm_weight.uint16.le.bin", "<u2", [epochs, HIDDEN], (_bf16_epoch(epoch, HIDDEN, 0x44) for epoch in range(epochs))),
    }
    records = {name: _record(name, file_name, dtype, shape, _write_epochs(root / file_name, blobs)) for name, (file_name, dtype, shape, blobs) in specs.items()}
    route_map = b"".join(struct.pack("<i", value) for value in range(80))
    _write_bytes_exclusive(root / "canonical_route_map.int32.le.bin", route_map)
    fixtures = []
    for epoch, epoch_masks in enumerate(masks):
        fixture_class = (
            "coverage_and_witnesses"
            if epoch == 0
            else (
                "all_remote_zero"
                if epoch == 1
                else (
                    "independent_slot_probe"
                    if epoch <= 11
                    else "deterministic_mask_rotation"
                )
            )
        )
        fixtures.append({"id": f"epoch-{epoch:03d}", "phase": "pre_timing" if epoch < PRE_TIMING_EPOCHS else "post_timing", "class": fixture_class, "local_masks_uint16": epoch_masks, "route_pattern": "all_local" if all(value == 0x03FF for value in epoch_masks) else ("all_remote_zero" if all(value == 0 for value in epoch_masks) else "mixed_local_zero"), "independent_slot_probes": [epoch - 2] if 2 <= epoch <= 11 else [], "tensor_sha256": {name: value["epoch_sha256"][epoch] for name, value in records.items()}})
    manifest: dict[str, Any] = {"format": FORMAT, "production": not test_only, "pre_timing_epochs": PRE_TIMING_EPOCHS if not test_only else None, "post_timing_epochs": POST_TIMING_EPOCHS if not test_only else None, "epochs": epochs, "geometry": {"tokens": TOKENS, "topk": TOPK, "hidden": HIDDEN, "ranks": RANKS}, "canonical_route_map": {"file": "canonical_route_map.int32.le.bin", "dtype": "<i4", "shape": [TOKENS, TOPK], "sha256": hashlib.sha256(route_map).hexdigest(), "definition": "arange(80).reshape(8,10)"}, "local_masks_uint16": masks, "fixtures": fixtures, "classes": {"row_generation": "uint16_arange_mod_65536_then_literal_remote_zero", "fp32_inventory": ["positive_zero", "negative_zero", "positive_subnormal", "negative_subnormal", "one_minus_ulp", "one_plus_ulp", "representative_large_finite", "negative_representative_large_finite", "positive_max_finite", "negative_max_finite", "positive_infinity", "negative_infinity", "positive_payload_nan", "negative_payload_nan"], "witnesses": ["ordered_cancellation", "bf16_midpoint"]}, "tensors": records}
    _write_canonical_exclusive(root / "manifest.json", manifest)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return manifest


def prepare_production(output_root: Path) -> dict[str, Any]:
    return _write_fixture(output_root, EPOCHS, test_only=False)


def _write_test_fixture(output_root: Path, epochs: int = 4) -> dict[str, Any]:
    if epochs < 2:
        raise ValueError("test corpus needs at least two epochs")
    return _write_fixture(output_root, epochs, test_only=True)


def _tensor_specs(epochs: int) -> dict[str, tuple[str, str, list[int]]]:
    return {
        "route_rows": ("route_rows.uint16.le.bin", "<u2", [epochs, 80, HIDDEN]),
        "weights": ("weights.uint32.le.bin", "<u4", [epochs, TOKENS, TOPK]),
        "scale_add_input": ("scale_add_input.uint16.le.bin", "<u2", [epochs, TOKENS, HIDDEN]),
        "four_rank_tail": ("four_rank_tail.uint16.le.bin", "<u2", [epochs, RANKS - 1, TOKENS, HIDDEN]),
        "residual_input": ("residual_input.uint16.le.bin", "<u2", [epochs, TOKENS, HIDDEN]),
        "norm_weight": ("norm_weight.uint16.le.bin", "<u2", [epochs, HIDDEN]),
    }


def _expected_blob(name: str, epoch: int, masks: list[list[int]]) -> bytes:
    if name == "route_rows":
        return _row_epoch(epoch, masks[epoch])
    if name == "weights":
        return _weights_epoch(epoch)
    words_and_salt = {
        "scale_add_input": (TOKENS * HIDDEN, 0x11),
        "four_rank_tail": ((RANKS - 1) * TOKENS * HIDDEN, 0x22),
        "residual_input": (TOKENS * HIDDEN, 0x33),
        "norm_weight": (HIDDEN, 0x44),
    }
    words, salt = words_and_salt[name]
    return _bf16_epoch(epoch, words, salt)


def _expected_hashes(name: str, epochs: int, masks: list[list[int]]) -> tuple[str, list[str]]:
    whole = hashlib.sha256()
    per_epoch: list[str] = []
    for epoch in range(epochs):
        blob = _expected_blob(name, epoch, masks)
        whole.update(blob)
        per_epoch.append(hashlib.sha256(blob).hexdigest())
    return whole.hexdigest(), per_epoch


def _checked_record(root: Path, spec: tuple[str, str, list[int]]) -> tuple[str, list[str]]:
    file_name, dtype, shape = spec
    width = {"<u2": 2, "<u4": 4}[dtype]
    path = root / file_name
    epoch_bytes = width
    for value in shape[1:]:
        epoch_bytes *= value
    with _open_regular(path) as handle:
        if os.fstat(handle.fileno()).st_size != epoch_bytes * shape[0]:
            raise ValueError(f"wrong binary size: {path}")
    return _sha_file(path), [_sha_file(path, index * epoch_bytes, epoch_bytes) for index in range(shape[0])]


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _bf16_to_f32(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits << 16))[0]


def _ordered_bf16(rows: list[int], weights: list[int]) -> int:
    accum = _f32(0.0)
    for row, weight in zip(rows, weights, strict=True):
        accum = _f32(accum + _f32(_bf16_to_f32(row) * struct.unpack("<f", struct.pack("<I", weight))[0]))
    bits = struct.unpack("<I", struct.pack("<f", accum))[0]
    # Round-to-nearest-even FP32 -> BF16, preserving signed zero.
    return ((bits + 0x7FFF + ((bits >> 16) & 1)) >> 16) & 0xFFFF


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _analyze(output_root: Path, *, allow_test_fixture: bool) -> dict[str, Any]:
    """Re-read binaries with mmap and recompute all evidence without trusting claims."""
    root = _require_root(output_root)
    manifest_path = root / "manifest.json"
    try:
        raw_manifest = _read_bounded_regular(
            manifest_path,
            MAX_MANIFEST_BYTES,
        ).decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("manifest is not UTF-8") from error
    manifest = json.loads(raw_manifest)
    expected_top_level = {"format", "production", "pre_timing_epochs", "post_timing_epochs", "epochs", "geometry", "canonical_route_map", "local_masks_uint16", "fixtures", "classes", "tensors"}
    if not isinstance(manifest, dict) or set(manifest) != expected_top_level or manifest.get("format") != FORMAT or type(manifest.get("production")) is not bool:
        raise ValueError("invalid frozen manifest schema")
    if type(manifest.get("epochs")) is not int:
        raise ValueError("manifest epochs must be an exact integer")
    epochs = manifest["epochs"]
    if manifest["production"] is not True and not allow_test_fixture:
        raise ValueError("analyze_existing accepts production manifests only")
    if epochs < 13 or (manifest["production"] and epochs != EPOCHS):
        raise ValueError("invalid frozen epoch count")
    timing_counts = (
        manifest["pre_timing_epochs"],
        manifest["post_timing_epochs"],
    )
    if manifest["production"]:
        if (
            any(type(value) is not int for value in timing_counts)
            or timing_counts != (PRE_TIMING_EPOCHS, POST_TIMING_EPOCHS)
        ):
            raise ValueError("invalid frozen production timing counts")
    elif timing_counts != (None, None):
        raise ValueError("test fixture timing counts must be null")
    if raw_manifest != json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n":
        raise ValueError("manifest is not canonical JSON")
    expected_classes = {"row_generation": "uint16_arange_mod_65536_then_literal_remote_zero", "fp32_inventory": ["positive_zero", "negative_zero", "positive_subnormal", "negative_subnormal", "one_minus_ulp", "one_plus_ulp", "representative_large_finite", "negative_representative_large_finite", "positive_max_finite", "negative_max_finite", "positive_infinity", "negative_infinity", "positive_payload_nan", "negative_payload_nan"], "witnesses": ["ordered_cancellation", "bf16_midpoint"]}
    if manifest.get("classes") != expected_classes:
        raise ValueError("manifest classes drift")
    expected_geometry = {
        "tokens": TOKENS,
        "topk": TOPK,
        "hidden": HIDDEN,
        "ranks": RANKS,
    }
    if (
        manifest["geometry"] != expected_geometry
        or not all(type(value) is int for value in manifest["geometry"].values())
    ):
        raise ValueError("unexpected frozen geometry")
    map_spec = {"file": "canonical_route_map.int32.le.bin", "dtype": "<i4", "shape": [TOKENS, TOPK], "definition": "arange(80).reshape(8,10)"}
    map_record = manifest.get("canonical_route_map")
    if (
        not isinstance(map_record, dict)
        or set(map_record) != {*map_spec, "sha256"}
        or any(map_record.get(key) != value for key, value in map_spec.items())
        or not all(type(value) is int for value in map_record.get("shape", []))
        or not _is_sha256(map_record.get("sha256"))
    ):
        raise ValueError("manifest canonical map specification drift")
    specs = _tensor_specs(epochs)
    if not isinstance(manifest.get("tensors"), dict) or set(manifest["tensors"]) != set(specs):
        raise ValueError("unexpected tensor schema")
    for name, (file_name, dtype, shape) in specs.items():
        record = manifest["tensors"][name]
        if (
            not isinstance(record, dict)
            or set(record)
            != {"name", "file", "dtype", "shape", "sha256", "epoch_sha256"}
            or (record["name"], record["file"], record["dtype"], record["shape"])
            != (name, file_name, dtype, shape)
            or not all(type(value) is int for value in record["shape"])
            or not _is_sha256(record["sha256"])
            or not isinstance(record["epoch_sha256"], list)
            or len(record["epoch_sha256"]) != epochs
            or not all(_is_sha256(value) for value in record["epoch_sha256"])
        ):
            raise ValueError("manifest tensor specification drift")
    expected_masks = _masks(epochs)
    manifest_masks = manifest.get("local_masks_uint16")
    if (
        manifest_masks != expected_masks
        or not isinstance(manifest_masks, list)
        or not all(
            isinstance(row, list)
            and len(row) == TOKENS
            and all(type(value) is int for value in row)
            for row in manifest_masks
        )
    ):
        raise ValueError("manifest mask schedule drift")
    expected_ids = [f"epoch-{index:03d}" for index in range(epochs)]
    fixtures = manifest.get("fixtures")
    if (
        not isinstance(fixtures, list)
        or len(fixtures) != epochs
        or not all(isinstance(fixture, dict) for fixture in fixtures)
        or [fixture.get("id") for fixture in fixtures] != expected_ids
    ):
        raise ValueError("manifest fixture ID drift")
    if [fixture.get("phase") for fixture in fixtures] != ["pre_timing" if index < PRE_TIMING_EPOCHS else "post_timing" for index in range(epochs)]:
        raise ValueError("manifest fixture phase drift")
    fixture_keys = {
        "id",
        "phase",
        "class",
        "local_masks_uint16",
        "route_pattern",
        "independent_slot_probes",
        "tensor_sha256",
    }
    for index, fixture in enumerate(fixtures):
        values = expected_masks[index]
        expected_pattern = "all_local" if all(value == 0x03FF for value in values) else ("all_remote_zero" if all(value == 0 for value in values) else "mixed_local_zero")
        expected_class = (
            "coverage_and_witnesses"
            if index == 0
            else (
                "all_remote_zero"
                if index == 1
                else (
                    "independent_slot_probe"
                    if index <= 11
                    else "deterministic_mask_rotation"
                )
            )
        )
        tensor_hashes = fixture.get("tensor_sha256")
        if (
            set(fixture) != fixture_keys
            or fixture.get("class") != expected_class
            or fixture.get("local_masks_uint16") != values
            or not all(type(value) is int for value in fixture["local_masks_uint16"])
            or fixture.get("route_pattern") != expected_pattern
            or fixture.get("independent_slot_probes")
            != ([index - 2] if 2 <= index <= 11 else [])
            or not isinstance(tensor_hashes, dict)
            or set(tensor_hashes) != set(specs)
            or not all(_is_sha256(value) for value in tensor_hashes.values())
        ):
            raise ValueError("manifest fixture class drift")
    actual = {name: _checked_record(root, spec) for name, spec in specs.items()}
    deterministic = {name: _expected_hashes(name, epochs, expected_masks) for name in specs}
    deterministic_bytes_match = all(actual[name] == deterministic[name] for name in specs)
    hashes_match = all(actual[name][0] == record["sha256"] and actual[name][1] == record["epoch_sha256"] for name, record in manifest["tensors"].items())
    fixture_hashes_match = all(fixture["tensor_sha256"] == {name: actual[name][1][index] for name in actual} for index, fixture in enumerate(manifest["fixtures"]))
    rows_path = root / specs["route_rows"][0]
    coverage = bytearray(65536)
    actual_masks: list[list[int]] = []
    local_formula = True
    with _open_regular(rows_path) as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for (value,) in struct.iter_unpack("<H", data):
            coverage[value] = 1
        witness_rows0 = [struct.unpack_from("<H", data, row * HIDDEN * 2)[0] for row in range(10)]
        witness_rows1 = [struct.unpack_from("<H", data, (10 + row) * HIDDEN * 2 + 2)[0] for row in range(10)]
        for epoch in range(epochs):
            observed: list[int] = []
            expected_epoch = _row_epoch(epoch, expected_masks[epoch])
            for row in range(80):
                start = (epoch * 80 + row) * HIDDEN * 2
                raw_row = data[start : start + HIDDEN * 2]
                expected_row = expected_epoch[row * HIDDEN * 2 : (row + 1) * HIDDEN * 2]
                token, slot = divmod(row, TOPK)
                if expected_masks[epoch][token] & (1 << slot) and raw_row == expected_row and raw_row != b"\0" * (HIDDEN * 2):
                    observed.append(1)
                elif not expected_masks[epoch][token] & (1 << slot) and raw_row == b"\0" * (HIDDEN * 2):
                    observed.append(0)
                else:
                    observed.append(-1)
                    local_formula = False
            actual_masks.append([sum((1 << slot) for slot in range(TOPK) if observed[token * TOPK + slot] == 1) for token in range(TOKENS)])
    masks = actual_masks
    zero_rows = True
    epoch_bytes, row_bytes = 80 * HIDDEN * 2, HIDDEN * 2
    with _open_regular(rows_path) as handle:
        for epoch, values in enumerate(masks):
            for token, mask in enumerate(values):
                for slot in range(TOPK):
                    if not mask & (1 << slot):
                        handle.seek(epoch * epoch_bytes + (token * TOPK + slot) * row_bytes)
                        zero_rows &= handle.read(row_bytes) == b"\0" * row_bytes
    weights_path = root / specs["weights"][0]
    wanted = {0: "positive_zero", 0x80000000: "negative_zero", 1: "positive_subnormal", 0x80000001: "negative_subnormal", 0x3F7FFFFF: "one_minus_ulp", 0x3F800001: "one_plus_ulp", 0x7F000000: "representative_large_finite", 0xFF000000: "negative_representative_large_finite", 0x7F7FFFFF: "positive_max_finite", 0xFF7FFFFF: "negative_max_finite", 0x7F800000: "positive_infinity", 0xFF800000: "negative_infinity", 0x7FC00001: "positive_payload_nan", 0xFFC12345: "negative_payload_nan"}
    seen: set[str] = set()
    with _open_regular(weights_path) as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for (value,) in struct.iter_unpack("<I", data):
            if value in wanted:
                seen.add(wanted[value])
        witness_weights0 = list(struct.unpack_from("<10I", data, 0))
        witness_weights1 = list(struct.unpack_from("<10I", data, 10 * 4))
    cancellation = witness_rows0[:2] == [0x3F80, 0xBF80] and witness_weights0 == [0x3F800000, 0x3F800000] + [0] * 8 and _ordered_bf16(witness_rows0, witness_weights0) == 0
    midpoint = witness_rows1[:2] == [0x3F80, 0x3F80] and witness_weights1 == [0x3F800000, 0x3B800000] + [0] * 8 and _ordered_bf16(witness_rows1, witness_weights1) == 0x3F80
    route_map = _read_bounded_regular(
        root / "canonical_route_map.int32.le.bin",
        TOKENS * TOPK * 4,
    )
    if len(route_map) != TOKENS * TOPK * 4:
        raise ValueError("wrong canonical route-map size")
    canonical = route_map == b"".join(struct.pack("<i", value) for value in range(80))
    hashes_match &= manifest["canonical_route_map"].get("sha256") == hashlib.sha256(route_map).hexdigest()
    all_masks = set(range(1024)).issubset({value for row in masks for value in row})
    probe_ok = True
    with _open_regular(weights_path) as handle:
        for epoch in range(2, 12):
            handle.seek(epoch * 80 * 4)
            values = struct.unpack("<80I", handle.read(80 * 4))
            slot = epoch - 2
            probe_ok &= all(value == (0x3F800000 if index % TOPK == slot else 0) for index, value in enumerate(values))
    return {"manifest_sha256": _sha_file(manifest_path), "hashes_match_manifest": hashes_match and fixture_hashes_match, "deterministic_bytes_match": deterministic_bytes_match, "tensors": {name: {"sha256": values[0], "epoch_sha256": values[1]} for name, values in actual.items()}, "coverage": {"uint16_patterns_present": sum(coverage), "all_65536": all(coverage), "fp32_classes_present": sorted(seen), "all_fp32_edge_classes": seen == set(wanted.values()), "all_1024_local_zero_masks": all_masks, "all_slots_independently_active": probe_ok, "all_local": any(all(value == 0x03FF for value in row) for row in masks), "all_remote_zero": any(all(value == 0 for value in row) for row in masks), "zero_rows_literal_uint16_zero": zero_rows, "local_rows_match_formula": local_formula and masks == expected_masks, "canonical_route_map": canonical, "ordered_cancellation_witness": cancellation, "bf16_midpoint_witness": midpoint}}


def analyze_existing(output_root: Path) -> dict[str, Any]:
    """Independently audit only the fixed, production Phase-A corpus."""
    report = _analyze(output_root, allow_test_fixture=False)
    required_coverage = (
        "all_65536",
        "all_fp32_edge_classes",
        "all_1024_local_zero_masks",
        "all_slots_independently_active",
        "all_local",
        "all_remote_zero",
        "zero_rows_literal_uint16_zero",
        "local_rows_match_formula",
        "canonical_route_map",
        "ordered_cancellation_witness",
        "bf16_midpoint_witness",
    )
    if (
        report["hashes_match_manifest"] is not True
        or report["deterministic_bytes_match"] is not True
        or any(report["coverage"].get(key) is not True for key in required_coverage)
        or report["coverage"]["uint16_patterns_present"] != 65536
    ):
        raise ValueError("production fixture proof failed closed")
    return {**report, "status": "passed"}


def _analyze_test_fixture(output_root: Path) -> dict[str, Any]:
    """Internal test-only entry point for small fixtures; never wired to the CLI."""
    return _analyze(output_root, allow_test_fixture=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--analyze-existing", action="store_true")
    args = parser.parse_args()
    if args.analyze_existing:
        report = analyze_existing(args.output_root)
        _write_canonical_exclusive(
            _require_root(args.output_root) / "analysis.json",
            report,
        )
    else:
        report = prepare_production(args.output_root)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

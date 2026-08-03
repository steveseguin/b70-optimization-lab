#!/usr/bin/env python3
"""Validate exact-small worker selector records and grouped-GEMM mappings."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

MARKER = "LAGUNA_EXACT_SMALL_WORKER_SELECTORS_V1"
SCHEMA = "laguna-exact-small-worker-selectors-v1"
LATENCY_MARKER = "LAGUNA_EXACT_SMALL_WORKER_SELECTORS_V2"
LATENCY_SCHEMA = "laguna-exact-small-worker-selectors-v2"
EXPECTED_SELECTORS = {
    "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "11",
    "LAGUNA_LOG_MOE_ROWS": "1",
    "LAGUNA_M": "12",
    "LAGUNA_SPEC": "11",
    "VLLM_XPU_LAGUNA_DECODE_GRF128": "1",
    "VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS": "1",
    "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES": "1",
    "VLLM_XPU_LAGUNA_DEQUANT_MAD": "0",
    "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE": "1",
    "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16": "1",
    "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS": "1",
    "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH": "1",
    "VLLM_XPU_LAGUNA_EXACT_MAX_M": "12",
    "VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD": "1",
    "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE": "1",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "1",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
    "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK": "1",
    "VLLM_XPU_LAGUNA_SCALE_FOLD": "0",
    "VLLM_XPU_LAGUNA_SCALE_LANE_DEDUP": "1",
    "VLLM_XPU_LAGUNA_SCALE_VEC": "1",
}
LATENCY_EXPECTED_SELECTORS = {
    **EXPECTED_SELECTORS,
    "VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS": "1",
}
SELECTOR_CONTRACT_SHA256 = (
    "fef0594c56fb917c212af09b5b7573acf528bbcc4ebd46543179994282ba8f52"
)
LATENCY_SELECTOR_CONTRACT_SHA256 = (
    "5bf0319dfa3e931e66c8a1f8c5292b14cb1054cca7c65eb5763951a12ba9752b"
)
TOP_LEVEL_KEYS = {
    "schema",
    "pid",
    "pid_start_time_ticks",
    "worker_name",
    "world_size",
    "ranks",
    "selector_contract_sha256",
    "selector_count",
    "selectors",
}
RANK_KEYS = {"global", "local", "tp", "ep"}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def _load_record(
    encoded: str,
    *,
    schema: str,
    expected_selectors: dict[str, str],
    expected_contract_sha256: str,
) -> dict[str, Any]:
    value = json.loads(
        encoded,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonfinite,
    )
    if not isinstance(value, dict):
        raise ValueError("worker selector evidence must be a JSON object")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    if encoded != canonical:
        raise ValueError("worker selector evidence JSON is not canonical")
    if set(value) != TOP_LEVEL_KEYS:
        raise ValueError("worker selector evidence top-level fields drifted")
    if value["schema"] != schema:
        raise ValueError("worker selector evidence schema drifted")
    if value["selector_contract_sha256"] != expected_contract_sha256:
        raise ValueError("worker selector evidence contract hash drifted")
    if type(value["selector_count"]) is not int or value["selector_count"] != len(
        expected_selectors
    ):
        raise ValueError("worker selector evidence selector count drifted")

    ranks = value["ranks"]
    if not isinstance(ranks, dict) or set(ranks) != RANK_KEYS:
        raise ValueError("worker selector evidence rank fields drifted")
    integer_fields = {
        "pid": value["pid"],
        "pid_start_time_ticks": value["pid_start_time_ticks"],
        "world_size": value["world_size"],
        **ranks,
    }
    if any(type(field) is not int for field in integer_fields.values()):
        raise ValueError("worker selector evidence identity fields must be integers")
    if value["pid"] <= 0 or value["pid_start_time_ticks"] <= 0:
        raise ValueError("worker selector evidence process identity is invalid")
    if value["world_size"] != 4:
        raise ValueError("worker selector evidence world size is not four")
    rank = ranks["global"]
    if rank not in range(4) or any(rank_value != rank for rank_value in ranks.values()):
        raise ValueError(
            "worker selector evidence rank identity is not diagonal TP4/EP4"
        )
    if value["worker_name"] != f"Worker_TP{rank}_EP{rank}":
        raise ValueError("worker selector evidence process name disagrees with rank")
    if value["selectors"] != expected_selectors:
        raise ValueError("worker selector evidence values differ from the frozen map")
    return value


def parse_worker_selector_log(
    log_path: Path, *, require_exact_prefill: bool = False
) -> list[dict[str, Any]]:
    marker_name = LATENCY_MARKER if require_exact_prefill else MARKER
    schema = LATENCY_SCHEMA if require_exact_prefill else SCHEMA
    expected_selectors = (
        LATENCY_EXPECTED_SELECTORS if require_exact_prefill else EXPECTED_SELECTORS
    )
    expected_contract_sha256 = (
        LATENCY_SELECTOR_CONTRACT_SHA256
        if require_exact_prefill
        else SELECTOR_CONTRACT_SHA256
    )
    if selector_contract_sha256(expected_selectors) != expected_contract_sha256:
        raise ValueError("frozen worker selector contract hash drifted")
    records = []
    marker = marker_name + " "
    for line in log_path.read_text(encoding="utf-8", errors="strict").splitlines():
        if marker not in line:
            continue
        _, encoded = line.split(marker, 1)
        records.append(
            _load_record(
                encoded,
                schema=schema,
                expected_selectors=expected_selectors,
                expected_contract_sha256=expected_contract_sha256,
            )
        )

    if len(records) != 4:
        raise ValueError(f"expected four worker selector records, found {len(records)}")
    records.sort(key=lambda record: record["ranks"]["global"])
    if [record["ranks"]["global"] for record in records] != list(range(4)):
        raise ValueError(
            "worker selector evidence rank set is incomplete or duplicated"
        )
    pids = [record["pid"] for record in records]
    if len(set(pids)) != 4:
        raise ValueError("worker selector evidence PIDs are not unique")
    return records


def selector_contract_sha256(
    selectors: dict[str, str] = EXPECTED_SELECTORS,
) -> str:
    payload = "".join(
        f"{name}={value}\n" for name, value in sorted(selectors.items())
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def parse_linux_process_start_time(stat_line: str) -> int:
    _, separator, fields = stat_line.rpartition(")")
    if not separator:
        raise ValueError("process stat has no closing command delimiter")
    tail = fields.split()
    if len(tail) < 20:
        raise ValueError("process stat is missing the start-time field")
    try:
        start_time = int(tail[19])
    except ValueError as exc:
        raise ValueError("process stat start time is not an integer") from exc
    if start_time <= 0:
        raise ValueError("process stat start time must be positive")
    return start_time


def _read_start_time(proc_root: Path, pid: int) -> int:
    return parse_linux_process_start_time(
        (proc_root / str(pid) / "stat").read_text(encoding="utf-8")
    )


def _sha256_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while block := os.read(fd, 1024 * 1024):
        digest.update(block)
    return digest.hexdigest()


def _fd_metadata(fd: int) -> os.stat_result:
    try:
        return os.fstat(fd)
    except OSError as original_error:
        try:
            return Path(f"/proc/self/fd/{fd}").stat()
        except OSError:
            raise original_error


def verify_grouped_gemm_maps(
    records: list[dict[str, Any]],
    *,
    proc_root: Path,
    expected_dso: Path,
    expected_sha256: str,
) -> list[dict[str, Any]]:
    expected_path = expected_dso.resolve(strict=True)
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    expected_fd = os.open(expected_path, flags)
    try:
        expected_metadata = _fd_metadata(expected_fd)
        expected_identity = (expected_metadata.st_dev, expected_metadata.st_ino)
        if not stat.S_ISREG(expected_metadata.st_mode):
            raise ValueError("expected grouped-GEMM DSO is not a regular file")
        expected_device = (
            os.major(expected_metadata.st_dev),
            os.minor(expected_metadata.st_dev),
        )
        expected_inode = expected_metadata.st_ino
        if _sha256_fd(expected_fd) != expected_sha256:
            raise ValueError("expected grouped-GEMM DSO hash drifted")

        summaries = []
        for record in records:
            pid = record["pid"]
            expected_start_time = record["pid_start_time_ticks"]
            if _read_start_time(proc_root, pid) != expected_start_time:
                raise ValueError(f"worker {pid} start time drifted before maps proof")
            mapped_files = {
                (
                    Path(fields[5]),
                    tuple(int(part, 16) for part in fields[3].split(":")),
                    int(fields[4]),
                )
                for line in (proc_root / str(pid) / "maps")
                .read_text(encoding="utf-8")
                .splitlines()
                if len(fields := line.split(maxsplit=5)) == 6
                and fields[5].startswith("/")
                and fields[5].endswith("/libgrouped_gemm_xe_2.so")
            }
            if len(mapped_files) != 1:
                raise ValueError(
                    f"worker {pid} did not map exactly one grouped-GEMM DSO"
                )
            mapped_path_raw, mapped_device, mapped_inode = next(iter(mapped_files))
            mapped_path = mapped_path_raw.resolve(strict=True)
            if mapped_path != expected_path:
                raise ValueError(f"worker {pid} mapped the wrong grouped-GEMM DSO")
            if mapped_device != expected_device or mapped_inode != expected_inode:
                raise ValueError(f"worker {pid} mapped grouped-GEMM DSO inode drifted")
            if _read_start_time(proc_root, pid) != expected_start_time:
                raise ValueError(f"worker {pid} start time drifted after maps proof")
            summaries.append(
                {
                    "global_rank": record["ranks"]["global"],
                    "pid": pid,
                    "pid_start_time_ticks": expected_start_time,
                    "path": str(mapped_path),
                    "device_major": expected_device[0],
                    "device_minor": expected_device[1],
                    "inode": expected_inode,
                    "sha256": expected_sha256,
                }
            )

        if _sha256_fd(expected_fd) != expected_sha256:
            raise ValueError("expected grouped-GEMM DSO hash drifted after maps proof")
        final_metadata = _fd_metadata(expected_fd)
        if (final_metadata.st_dev, final_metadata.st_ino) != expected_identity:
            raise ValueError("expected grouped-GEMM DSO descriptor identity drifted")
        final_path_metadata = expected_path.lstat()
        if (
            final_path_metadata.st_dev,
            final_path_metadata.st_ino,
        ) != expected_identity:
            raise ValueError("expected grouped-GEMM DSO pathname identity drifted")
        return summaries
    finally:
        os.close(expected_fd)


def _unlink_if_same(path: Path, identity: tuple[int, int]) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return True
    if (metadata.st_dev, metadata.st_ino) != identity:
        return False
    path.unlink()
    return True


def write_canonical_jsonl(path: Path, records: list[dict[str, Any]]) -> tuple[int, int]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    identity = None
    try:
        metadata = _fd_metadata(fd)
        identity = (metadata.st_dev, metadata.st_ino)
        os.fchmod(fd, 0o600)
        metadata = _fd_metadata(fd)
        if (metadata.st_dev, metadata.st_ino) != identity:
            raise ValueError("worker evidence output identity drifted after chmod")
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or metadata.st_uid != os.getuid()
            or metadata.st_gid != os.getgid()
        ):
            raise ValueError("worker evidence output identity is unsafe")
        payload = "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ).encode("ascii")
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise OSError("worker evidence output write made no progress")
            offset += written
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        fd = -1
        if identity is not None:
            _unlink_if_same(path, identity)
        raise
    finally:
        if fd >= 0:
            os.close(fd)
    assert identity is not None
    return identity


def write_evidence_pair(
    selector_path: Path,
    selector_records: list[dict[str, Any]],
    map_path: Path,
    map_records: list[dict[str, Any]],
) -> None:
    if selector_path.resolve(strict=False) == map_path.resolve(strict=False):
        raise ValueError("selector and map outputs must be distinct")
    for path in (selector_path, map_path):
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        raise FileExistsError(path)

    selector_identity = write_canonical_jsonl(selector_path, selector_records)
    try:
        map_identity = write_canonical_jsonl(map_path, map_records)
    except BaseException:
        if not _unlink_if_same(selector_path, selector_identity):
            raise RuntimeError(
                "map publication failed and selector output identity drifted"
            )
        raise

    try:
        for path, identity in (
            (selector_path, selector_identity),
            (map_path, map_identity),
        ):
            metadata = path.lstat()
            if (metadata.st_dev, metadata.st_ino) != identity:
                raise RuntimeError("published worker evidence identity drifted")
    except BaseException:
        _unlink_if_same(selector_path, selector_identity)
        _unlink_if_same(map_path, map_identity)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--selector-output", type=Path, required=True)
    parser.add_argument("--map-output", type=Path, required=True)
    parser.add_argument("--expected-dso", type=Path, required=True)
    parser.add_argument("--expected-dso-sha256", required=True)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    parser.add_argument("--require-exact-prefill", action="store_true")
    args = parser.parse_args()

    expected_selectors = (
        LATENCY_EXPECTED_SELECTORS if args.require_exact_prefill else EXPECTED_SELECTORS
    )
    expected_contract_sha256 = (
        LATENCY_SELECTOR_CONTRACT_SHA256
        if args.require_exact_prefill
        else SELECTOR_CONTRACT_SHA256
    )
    if selector_contract_sha256(expected_selectors) != expected_contract_sha256:
        raise ValueError("frozen worker selector contract hash drifted")

    records = parse_worker_selector_log(
        args.server_log, require_exact_prefill=args.require_exact_prefill
    )
    maps = verify_grouped_gemm_maps(
        records,
        proc_root=args.proc_root,
        expected_dso=args.expected_dso,
        expected_sha256=args.expected_dso_sha256,
    )
    write_evidence_pair(args.selector_output, records, args.map_output, maps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build deterministic exact-active-context token fixtures for Qwen 27B lanes.

The default mode is an inert plan. ``--write`` is the only mode that creates
an artifact, and it refuses an existing destination. ``--check`` regenerates
the expected artifact from the explicitly supplied tokenizer and source and
compares it byte-for-byte without modifying it.

This is grade-C fixture construction: source token IDs are repeated and then
truncated to the requested depth. It creates exact token-count inputs; it does
not claim that synthetic repetition is representative of natural context.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
SCHEMA = "openai-token-depth-fixture-v1"
TOKENIZER_FILES = (
    "added_tokens.json",
    "chat_template.jinja",
    "config.json",
    "merges.txt",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "vocab.json",
)
SPECIAL_TOKEN_POLICIES = ("none", "bos", "eos", "bos-and-eos")


class ContractError(RuntimeError):
    """Raised when inputs cannot satisfy the exact-depth fixture contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def rendered_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def tokenizer_file_hashes(tokenizer_dir: Path) -> dict[str, str]:
    if not tokenizer_dir.is_dir():
        raise ContractError(f"tokenizer directory does not exist: {tokenizer_dir}")
    hashes: dict[str, str] = {}
    for name in TOKENIZER_FILES:
        path = tokenizer_dir / name
        if path.is_file():
            hashes[name] = file_sha256(path)
    for path in sorted(tokenizer_dir.glob("tokenization*.py")):
        if path.is_file():
            hashes[path.name] = file_sha256(path)
    if "tokenizer.json" not in hashes or "tokenizer_config.json" not in hashes:
        raise ContractError(
            "tokenizer identity is incomplete: tokenizer.json and "
            "tokenizer_config.json are required"
        )
    return dict(sorted(hashes.items()))


def load_tokenizer(tokenizer_dir: Path) -> tuple[Any, dict[str, str | None]]:
    try:
        import transformers
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise ContractError(
            "transformers is required; run in an environment that already provides it"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_dir,
        local_files_only=True,
        trust_remote_code=False,
        use_fast=True,
    )
    try:
        import tokenizers
    except ImportError:
        tokenizers_version = None
    else:
        tokenizers_version = getattr(tokenizers, "__version__", None)
    return tokenizer, {
        "transformers": getattr(transformers, "__version__", None),
        "tokenizers": tokenizers_version,
    }


def validate_token_ids(values: Any, *, where: str) -> list[int]:
    if not isinstance(values, (list, tuple)):
        raise ContractError(f"{where} did not produce a flat token-ID list")
    result: list[int] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ContractError(f"{where} token {index} is not a nonnegative integer")
        result.append(value)
    return result


def special_token_ids(tokenizer: Any, policy: str) -> tuple[list[int], list[int]]:
    prefix: list[int] = []
    suffix: list[int] = []
    if policy in {"bos", "bos-and-eos"}:
        bos = getattr(tokenizer, "bos_token_id", None)
        if isinstance(bos, bool) or not isinstance(bos, int) or bos < 0:
            raise ContractError(
                f"special-token policy {policy!r} requires bos_token_id"
            )
        prefix.append(bos)
    if policy in {"eos", "bos-and-eos"}:
        eos = getattr(tokenizer, "eos_token_id", None)
        if isinstance(eos, bool) or not isinstance(eos, int) or eos < 0:
            raise ContractError(
                f"special-token policy {policy!r} requires eos_token_id"
            )
        suffix.append(eos)
    return prefix, suffix


def exact_ids(
    source_ids: Sequence[int],
    depth: int,
    prefix_ids: Sequence[int],
    suffix_ids: Sequence[int],
) -> list[int]:
    if depth == 0:
        return []
    body_count = depth - len(prefix_ids) - len(suffix_ids)
    if body_count < 0:
        raise ContractError(f"depth {depth} cannot contain the selected special tokens")
    if body_count and not source_ids:
        raise ContractError("source text tokenized to zero IDs")
    repeats = (body_count + len(source_ids) - 1) // len(source_ids) if body_count else 0
    body = (list(source_ids) * repeats)[:body_count]
    result = list(prefix_ids) + body + list(suffix_ids)
    if len(result) != depth:
        raise AssertionError(
            f"internal exact-depth error: wanted {depth}, got {len(result)}"
        )
    return result


def build_payload(
    *,
    tokenizer_dir: Path,
    source_path: Path,
    fixture_id: str,
    logical_model: str,
    tokenizer_revision: str,
    special_token_policy: str,
    tokenizer: Any,
    runtime_versions: dict[str, str | None] | None = None,
    generator_path: Path | None = None,
) -> dict[str, Any]:
    if not fixture_id.strip():
        raise ContractError("fixture ID must be nonempty")
    if not logical_model.strip():
        raise ContractError("logical model must be nonempty")
    if not tokenizer_revision.strip():
        raise ContractError("tokenizer revision must be nonempty")
    if special_token_policy not in SPECIAL_TOKEN_POLICIES:
        raise ContractError(f"unsupported special-token policy: {special_token_policy}")
    if not source_path.is_file():
        raise ContractError(f"source does not exist: {source_path}")

    generator = (generator_path or Path(__file__)).resolve()
    source_bytes = source_path.read_bytes()
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(f"source is not valid UTF-8: {source_path}") from exc

    source_ids = validate_token_ids(
        tokenizer.encode(source_text, add_special_tokens=False),
        where="source tokenization",
    )
    if not source_ids:
        raise ContractError("source text tokenized to zero IDs")
    prefix_ids, suffix_ids = special_token_ids(tokenizer, special_token_policy)

    cases = []
    for depth in DEPTHS:
        input_ids = exact_ids(source_ids, depth, prefix_ids, suffix_ids)
        cases.append(
            {
                "id": f"depth-{depth}",
                "depth": depth,
                "prompt_token_ids": input_ids,
                "prompt_token_ids_sha256": sha256_bytes(
                    canonical_json_bytes(input_ids)
                ),
                "token_count": len(input_ids),
            }
        )

    provenance: dict[str, Any] = {
        "evidence": {
            "grade": "C",
            "scope": "deterministic exact-token-count fixture construction",
            "representative_natural_context": False,
        },
        "generator": {
            "filename": generator.name,
            "sha256": file_sha256(generator),
        },
        "tokenizer": {
            "directory": str(tokenizer_dir.resolve()),
            "files_sha256": tokenizer_file_hashes(tokenizer_dir),
            "logical_model": logical_model,
            "revision": tokenizer_revision,
            "runtime_versions": runtime_versions or {},
        },
        "source": {
            "bytes": len(source_bytes),
            "path": str(source_path.resolve()),
            "sha256": sha256_bytes(source_bytes),
            "text_characters": len(source_text),
            "tokenization": {
                "add_special_tokens": False,
                "token_count": len(source_ids),
                "token_ids_sha256": sha256_bytes(canonical_json_bytes(source_ids)),
            },
        },
        "construction": {
            "active_context_definition": "length of the flat input_ids list",
            "depth_zero_policy": "empty input_ids; no special tokens",
            "policy": "repeat source token IDs cyclically, then truncate to exact depth",
            "special_token_policy": special_token_policy,
            "special_token_prefix_ids": prefix_ids,
            "special_token_suffix_ids": suffix_ids,
        },
    }
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": 1,
        "fixture_id": fixture_id,
        "depths": list(DEPTHS),
        "provenance": provenance,
        "provenance_sha256": sha256_bytes(canonical_json_bytes(provenance)),
        "cases": cases,
    }
    return payload


def atomic_create(path: Path, data: bytes) -> None:
    if path.exists():
        raise ContractError(f"refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ContractError(
                f"refusing to overwrite existing output: {path}"
            ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--fixture-id", required=True)
    parser.add_argument("--logical-model", required=True)
    parser.add_argument("--tokenizer-revision", required=True)
    parser.add_argument(
        "--special-token-policy",
        required=True,
        choices=SPECIAL_TOKEN_POLICIES,
    )
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--plan", action="store_true", help="build and summarize in memory"
    )
    mode.add_argument("--check", action="store_true", help="verify an existing output")
    mode.add_argument("--write", action="store_true", help="create a new output")
    return parser


def execute(
    args: argparse.Namespace,
    *,
    tokenizer_loader: Callable[
        [Path], tuple[Any, dict[str, str | None]]
    ] = load_tokenizer,
) -> dict[str, Any]:
    tokenizer, runtime_versions = tokenizer_loader(args.tokenizer_dir)
    payload = build_payload(
        tokenizer_dir=args.tokenizer_dir,
        source_path=args.source,
        fixture_id=args.fixture_id,
        logical_model=args.logical_model,
        tokenizer_revision=args.tokenizer_revision,
        special_token_policy=args.special_token_policy,
        tokenizer=tokenizer,
        runtime_versions=runtime_versions,
    )
    data = rendered_json_bytes(payload)
    mode = "check" if args.check else "write" if args.write else "plan"
    if mode == "check":
        if not args.output.is_file():
            raise ContractError(f"check output does not exist: {args.output}")
        if args.output.read_bytes() != data:
            raise ContractError(
                f"fixture differs from regenerated contract: {args.output}"
            )
    elif mode == "write":
        atomic_create(args.output, data)

    return {
        "artifact_sha256": sha256_bytes(data),
        "depths": list(DEPTHS),
        "mode": mode,
        "output": str(args.output),
        "status": "passed"
        if mode == "check"
        else "created"
        if mode == "write"
        else "planned",
    }


def main() -> None:
    parser = make_parser()
    try:
        summary = execute(parser.parse_args())
    except ContractError as exc:
        parser.error(str(exc))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

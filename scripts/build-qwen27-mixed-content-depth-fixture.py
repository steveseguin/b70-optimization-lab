#!/usr/bin/env python3
"""Build a frozen exact-depth fixture from several unrepeated repository texts.

This builder is intentionally separate from the historical repeated-token
fixture builder.  Each ``--source CLASS=RELATIVE_PATH`` becomes one case at
every canonical depth.  Source tokens are truncated, never repeated, and the
fixture records repository-relative source paths plus source, tokenizer, and
generator hashes.

The default mode is an inert plan. ``--write`` creates a new file and refuses
to overwrite it; ``--check`` regenerates and compares byte-for-byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence


DEPTHS = (2048, 4096, 8192, 16384, 24576, 32768)
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
CLASS_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class ContractError(RuntimeError):
    """Raised when fixture inputs do not satisfy the frozen contract."""


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
            "transformers is required; use an existing environment that provides it"
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


def parse_sources(repo_root: Path, specs: Sequence[str]) -> list[tuple[str, Path, str]]:
    root = repo_root.resolve()
    if not (root / ".git").exists():
        raise ContractError(f"repo root does not contain .git: {root}")
    if len(specs) < 3:
        raise ContractError("at least three differently classified sources are required")

    parsed: list[tuple[str, Path, str]] = []
    seen: set[str] = set()
    for spec in specs:
        label, separator, raw_path = spec.partition("=")
        if not separator or not CLASS_RE.fullmatch(label):
            raise ContractError(
                f"source must be CLASS=RELATIVE_PATH with a slug class: {spec!r}"
            )
        if label in seen:
            raise ContractError(f"duplicate source class: {label}")
        relative = Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError(f"source path must be repository-relative: {raw_path}")
        resolved = (root / relative).resolve()
        try:
            canonical_relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ContractError(f"source escapes repository root: {raw_path}") from exc
        if not resolved.is_file():
            raise ContractError(f"source does not exist: {canonical_relative}")
        seen.add(label)
        parsed.append((label, resolved, canonical_relative))
    return parsed


def build_payload(
    *,
    repo_root: Path,
    tokenizer_dir: Path,
    source_specs: Sequence[str],
    fixture_id: str,
    logical_model: str,
    tokenizer_repository: str,
    tokenizer_revision: str,
    tokenizer: Any,
    runtime_versions: dict[str, str | None] | None = None,
    generator_path: Path | None = None,
) -> dict[str, Any]:
    if not fixture_id.strip():
        raise ContractError("fixture ID must be nonempty")
    if not logical_model.strip():
        raise ContractError("logical model must be nonempty")
    if not tokenizer_repository.strip() or not tokenizer_revision.strip():
        raise ContractError("tokenizer repository and revision must be nonempty")

    root = repo_root.resolve()
    generator = (generator_path or Path(__file__)).resolve()
    sources = parse_sources(root, source_specs)
    cases: list[dict[str, Any]] = []
    provenance_sources: list[dict[str, Any]] = []

    for label, path, relative in sources:
        source_bytes = path.read_bytes()
        try:
            source_text = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractError(f"source is not valid UTF-8: {relative}") from exc
        source_ids = validate_token_ids(
            tokenizer.encode(source_text, add_special_tokens=False),
            where=f"{label} source tokenization",
        )
        if len(source_ids) < max(DEPTHS):
            raise ContractError(
                f"source {relative} has {len(source_ids)} tokens; "
                f"{max(DEPTHS)} are required without repetition"
            )
        provenance_sources.append(
            {
                "class": label,
                "path": relative,
                "bytes": len(source_bytes),
                "text_characters": len(source_text),
                "sha256": sha256_bytes(source_bytes),
                "tokenization": {
                    "add_special_tokens": False,
                    "token_count": len(source_ids),
                    "token_ids_sha256": sha256_bytes(canonical_json_bytes(source_ids)),
                },
            }
        )
        for depth in DEPTHS:
            prompt_ids = source_ids[:depth]
            cases.append(
                {
                    "id": f"{label}-depth-{depth}",
                    "class": label,
                    "depth": depth,
                    "prompt_token_ids": prompt_ids,
                    "prompt_token_ids_sha256": sha256_bytes(
                        canonical_json_bytes(prompt_ids)
                    ),
                    "token_count": len(prompt_ids),
                }
            )

    try:
        generator_relative = generator.relative_to(root).as_posix()
    except ValueError:
        generator_relative = generator.name
    provenance: dict[str, Any] = {
        "evidence": {
            "grade": "B",
            "scope": (
                "three-class exact-token context-shape fixture from unrepeated "
                "real repository prose, code, and structured documentation"
            ),
            "representative_natural_context": True,
            "natural_task_or_retrieval_prompt": False,
        },
        "generator": {
            "path": generator_relative,
            "sha256": file_sha256(generator),
        },
        "tokenizer": {
            "path_policy": "caller-supplied directory; reproduce from repository and revision",
            "repository": tokenizer_repository,
            "revision": tokenizer_revision,
            "files_sha256": tokenizer_file_hashes(tokenizer_dir),
            "logical_model": logical_model,
            "runtime_versions": runtime_versions or {},
        },
        "sources": provenance_sources,
        "construction": {
            "active_context_definition": "length of the flat input_ids list",
            "policy": "tokenize each source once without special tokens; truncate its unrepeated prefix to each exact depth",
            "source_classes": [label for label, _path, _relative in sources],
            "source_repetition": False,
            "special_tokens": False,
            "cases_per_depth": len(sources),
        },
    }
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "fixture_id": fixture_id,
        "depths": list(DEPTHS),
        "provenance": provenance,
        "provenance_sha256": sha256_bytes(canonical_json_bytes(provenance)),
        "cases": cases,
    }


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
            raise ContractError(f"refusing to overwrite existing output: {path}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--tokenizer-dir", required=True, type=Path)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--fixture-id", required=True)
    parser.add_argument("--logical-model", required=True)
    parser.add_argument("--tokenizer-repository", required=True)
    parser.add_argument("--tokenizer-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
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
        repo_root=args.repo_root,
        tokenizer_dir=args.tokenizer_dir,
        source_specs=args.source,
        fixture_id=args.fixture_id,
        logical_model=args.logical_model,
        tokenizer_repository=args.tokenizer_repository,
        tokenizer_revision=args.tokenizer_revision,
        tokenizer=tokenizer,
        runtime_versions=runtime_versions,
    )
    data = rendered_json_bytes(payload)
    mode = "check" if args.check else "write" if args.write else "plan"
    if mode == "check":
        if not args.output.is_file():
            raise ContractError(f"check output does not exist: {args.output}")
        if args.output.read_bytes() != data:
            raise ContractError(f"fixture differs from regenerated contract: {args.output}")
    elif mode == "write":
        atomic_create(args.output, data)
    return {
        "artifact_sha256": sha256_bytes(data),
        "cases": len(payload["cases"]),
        "classes": payload["provenance"]["construction"]["source_classes"],
        "depths": list(DEPTHS),
        "mode": mode,
        "output": str(args.output),
        "status": "passed" if mode == "check" else "created" if mode == "write" else "planned",
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

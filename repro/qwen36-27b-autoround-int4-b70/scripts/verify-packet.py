#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

SCRIPT = Path(__file__).resolve()
PACKET = SCRIPT.parent.parent
REPO = SCRIPT.parents[3]
SOURCE_PACKET = (
    REPO
    / "patches"
    / "qwen36-27b-autoround-int4-b70"
    / "record-20260711"
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum_file(directory: Path) -> None:
    subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS"], cwd=directory, check=True
    )


def verify_archive() -> None:
    archive = PACKET / "evidence" / "record-run-directories.tar.gz"
    manifest = PACKET / "evidence" / "record-run-directories.SHA256SUMS"
    expected: dict[str, str] = {}
    for line in manifest.read_text().splitlines():
        digest, name = line.split("  ", 1)
        expected[name.removeprefix("./")] = digest
    with tarfile.open(archive, "r:gz") as tar:
        all_members = tar.getmembers()
        for member in all_members:
            archive_path = PurePosixPath(member.name)
            check(not archive_path.is_absolute(), "archive contains an absolute path")
            check(".." not in archive_path.parts, "archive contains a parent traversal")
            check(
                member.isfile() or member.isdir(),
                f"archive contains a non-file entry: {member.name}",
            )
        members = {m.name: m for m in all_members if m.isfile()}
        check(set(members) == set(expected), "archive file list differs from manifest")
        for name, digest in expected.items():
            handle = tar.extractfile(members[name])
            check(handle is not None, f"cannot read archive member {name}")
            actual = hashlib.sha256(handle.read()).hexdigest()
            check(actual == digest, f"archive checksum mismatch: {name}")


def verify_evidence() -> None:
    expected = load(PACKET / "manifests" / "expected-result.json")
    strict = load(PACKET / "evidence" / "strict-realistic512.json")
    quality = load(PACKET / "evidence" / "quality-repeat128.json")
    crossover = load(PACKET / "evidence" / "crossover.json")
    metric = strict["summary"]["tok_s_1_100_after_ttft"]
    wanted = expected["primary_metric"]
    check(metric["median"] == wanted["median"], "headline median mismatch")
    check(metric["p10"] == wanted["p10"], "headline p10 mismatch")
    check(metric["mean"] == wanted["mean"], "headline mean mismatch")
    gate = strict["realistic_final_gate"]
    check(gate["passed"], "strict realistic gate did not pass")
    check(gate["cached_tokens_all_zero"], "cached token gate failed")
    check(gate["prompts_unique"], "prompt uniqueness gate failed")
    check(len(strict["rows"]) == 12, "strict suite does not have 12 rows")
    check(
        all(row["cached_tokens"] == 0 for row in strict["rows"]),
        "a strict row reports nonzero cached tokens",
    )
    check(
        len({row["prompt_sha256"] for row in strict["rows"]}) == 12,
        "strict prompt hashes are not unique",
    )
    check(quality["pass_all"], "quality pass_all is false")
    check(
        all(case["pass"] for case in quality["exact_cases"]),
        "an exact quality case failed",
    )
    check(quality["baseline_match_all"], "quality baseline parity failed")
    check(quality["repeat_case"]["pass"], "repeat128 failed")
    check(quality["repeat_case"]["repeats"] == 128, "repeat count is not 128")
    check(quality["long_context_case"]["pass"], "1K needle failed")
    rows = crossover["rows"]
    check(len(rows) == 4, "crossover does not have four rows")
    check(rows[0]["median_tok_s"] > rows[1]["median_tok_s"], "window 1 did not favor candidate")
    check(rows[2]["median_tok_s"] > rows[3]["median_tok_s"], "window 2 did not favor candidate")


def verify_source_artifacts() -> None:
    manifest = load(SOURCE_PACKET / "source-manifest.json")
    for key in ("vllm", "vllm_xpu_kernels"):
        item = manifest[key]
        check(
            sha256(SOURCE_PACKET / item["bundle"]) == item["bundle_sha256"],
            f"{key} bundle checksum mismatch",
        )
        check(
            sha256(SOURCE_PACKET / item["working_patch"])
            == item["working_patch_sha256"],
            f"{key} patch checksum mismatch",
        )
    for key in ("vllm", "vllm_xpu_kernels"):
        item = manifest[key]
        output = subprocess.check_output(
            ["git", "bundle", "list-heads", str(SOURCE_PACKET / item["bundle"])],
            text=True,
        ).splitlines()
        check(
            output == [f'{item["recorded_head"]} HEAD'],
            f"{key} bundle HEAD differs from the manifest",
        )


def main() -> int:
    verify_checksum_file(PACKET)
    verify_checksum_file(SOURCE_PACKET)
    verify_archive()
    verify_evidence()
    verify_source_artifacts()
    load(PACKET / "manifests" / "model.json")
    load(PACKET / "manifests" / "runtime.json")
    print("Qwen3.6-27B AutoRound INT4 TP2 repro packet: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

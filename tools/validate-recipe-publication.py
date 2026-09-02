#!/usr/bin/env python3
"""Validate that a published recipe is reproducible from public artifacts.

This validator intentionally separates publication from local reproducibility.
A recipe may work on the originating host while still failing this gate because
an input is untracked, a declared digest disagrees with its build script, or a
release asset is absent.  Use --check-remote for the final release audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
import zipfile


FORMAT = "neural.download.recipe-publication.v2"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
SCRIPT_REFERENCE_RE = re.compile(
    r"\$\{(?P<root>repo_root|script_dir)\}/(?P<path>[A-Za-z0-9_.+/@:-]+(?:/[A-Za-z0-9_.+/@:-]+)*)"
)
HOST_LOCAL_RE = re.compile(r"/(?:home/[^/]+|mnt/fast-ai|media/[^/]+)/")
REQUIRED_RELEASE_KINDS = {
    "build-log",
    "checksum-manifest",
    "wheel",
    "xpu-extension",
    "gdn-library",
    "runtime-inventory",
    "toolchain-inventory",
}
REQUIRED_BINARY_SECTIONS = {".text", ".rodata", ".data", "OFFLOAD_DEVICE_CODE"}
CRITICAL_BINARY_KINDS = {"xpu-extension", "gdn-library"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_tracked(repo: Path, path: PurePosixPath) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", "--", path.as_posix()],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _git_blob(repo: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _repo_path(repo: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty repository-relative path")
        return None
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        errors.append(f"{label} must stay inside the repository: {value!r}")
        return None
    path = repo / pure
    if not path.is_file():
        errors.append(f"{label} does not exist: {value}")
    elif not _is_tracked(repo, pure):
        errors.append(f"{label} is not tracked by Git: {value}")
    return path


def _read_shell_assignments(script: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in script.read_text().splitlines():
        match = ASSIGNMENT_RE.match(raw_line.strip())
        if not match:
            continue
        key, value = match.groups()
        values[key] = value.strip().strip('"\'')
    return values


def _resolve_shell_path(repo: Path, script: Path, value: str) -> Path | None:
    if value.startswith("${repo_root}/"):
        return repo / value.removeprefix("${repo_root}/")
    if value.startswith("${script_dir}/"):
        return script.parent / value.removeprefix("${script_dir}/")
    return None


def _validate_build_script(repo: Path, script: Path, errors: list[str]) -> None:
    label = script.relative_to(repo).as_posix()
    text = script.read_text()
    assignments = _read_shell_assignments(script)

    if HOST_LOCAL_RE.search(text):
        errors.append(f"{label}: contains an originating-host-only path")

    for match in SCRIPT_REFERENCE_RE.finditer(text):
        root = repo if match.group("root") == "repo_root" else script.parent
        referenced = root / match.group("path")
        try:
            relative = referenced.resolve().relative_to(repo.resolve())
        except ValueError:
            errors.append(f"{label}: referenced path escapes the repository: {referenced}")
            continue
        # Root-discovery expressions such as ${script_dir}/../.. intentionally
        # resolve to a directory. File closure is checked below; directory
        # references are navigation, not publishable artifacts.
        if referenced.is_dir():
            continue
        if not referenced.is_file():
            errors.append(f"{label}: referenced file does not exist: {relative.as_posix()}")
        elif not _is_tracked(repo, PurePosixPath(relative.as_posix())):
            errors.append(f"{label}: referenced file is not tracked: {relative.as_posix()}")

    # A digest beside a path in the same build script is an executable
    # contract. Validate the contract directly instead of duplicating it in a
    # second hand-maintained allow-list.
    for key, value in assignments.items():
        digest_key = f"{key}_sha256"
        expected = assignments.get(digest_key)
        if expected is None:
            continue
        path = _resolve_shell_path(repo, script, value)
        if path is None:
            continue
        if not SHA256_RE.fullmatch(expected):
            errors.append(f"{label}: {digest_key} is not a lowercase SHA-256 digest")
            continue
        if not path.is_file():
            errors.append(f"{label}: {key} does not resolve: {path}")
            continue
        actual = _sha256(path)
        if actual != expected:
            errors.append(
                f"{label}: {key} digest contract failed; expected {expected}, actual {actual}"
            )


def _validate_remote_asset(
    asset: dict[str, Any], errors: list[str], destination: Path | None = None
) -> None:
    name = asset["name"]
    request = Request(asset["url"], headers={"User-Agent": "neural-download-publication-audit/1"})
    digest = hashlib.sha256()
    size = 0
    try:
        with urlopen(request, timeout=60) as response:
            if destination is None:
                sink_context: Any = tempfile.TemporaryFile()
            else:
                sink_context = destination.open("wb")
            with sink_context as sink:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    sink.write(block)
                    digest.update(block)
                    size += len(block)
    except (HTTPError, URLError, TimeoutError) as exc:
        errors.append(f"release asset {name}: cannot download {asset['url']}: {exc}")
        return
    if size != asset["size"]:
        errors.append(f"release asset {name}: expected {asset['size']} bytes, downloaded {size}")
    if digest.hexdigest() != asset["sha256"]:
        errors.append(
            f"release asset {name}: expected SHA-256 {asset['sha256']}, downloaded {digest.hexdigest()}"
        )


def _verify_remote_binary(
    path: Path, declaration: dict[str, Any], errors: list[str]
) -> None:
    name = path.name
    if shutil.which("readelf") is None or shutil.which("objcopy") is None:
        errors.append(f"release asset {name}: readelf and objcopy are required for binary audit")
        return
    dynamic = subprocess.run(
        ["readelf", "-d", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    expected_runpath = declaration.get("runpath")
    if dynamic.returncode != 0:
        errors.append(f"release asset {name}: readelf failed: {dynamic.stderr.strip()}")
    elif f"Library runpath: [{expected_runpath}]" not in dynamic.stdout:
        errors.append(f"release asset {name}: RUNPATH does not match {expected_runpath!r}")

    sections = declaration.get("sections", {})
    for section, expected in sections.items():
        output = path.parent / f"{name}.{section.lstrip('.')}"
        result = subprocess.run(
            ["objcopy", "--dump-section", f"{section}={output}", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0 or not output.is_file():
            errors.append(f"release asset {name}: cannot extract section {section}")
            continue
        actual = _sha256(output)
        output.unlink()
        if actual != expected:
            errors.append(
                f"release asset {name}: section {section} expected {expected}, downloaded {actual}"
            )


def _verify_wheel_binary_closure(
    wheel: Path,
    binary_assets: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    try:
        with zipfile.ZipFile(wheel) as archive:
            members = archive.namelist()
            for name, asset in binary_assets.items():
                matches = [member for member in members if PurePosixPath(member).name == name]
                if len(matches) != 1:
                    errors.append(
                        f"release asset {wheel.name}: expected exactly one embedded {name}, found {len(matches)}"
                    )
                    continue
                digest = hashlib.sha256()
                with archive.open(matches[0]) as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != asset["sha256"]:
                    errors.append(
                        f"release asset {wheel.name}: embedded {name} does not match standalone asset"
                    )
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"release asset {wheel.name}: invalid wheel archive: {exc}")


def _verify_checksum_manifest(
    checksum_path: Path,
    assets: list[dict[str, Any]],
    errors: list[str],
) -> None:
    declared: dict[str, str] = {}
    try:
        for line in checksum_path.read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            name = name.lstrip("* ")
            if not SHA256_RE.fullmatch(digest) or not name:
                raise ValueError(line)
            declared[name] = digest
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        errors.append(f"release asset {checksum_path.name}: invalid checksum manifest: {exc}")
        return
    expected = {
        asset["name"]: asset["sha256"]
        for asset in assets
        if asset["kind"] != "checksum-manifest"
    }
    if declared != expected:
        missing = sorted(set(expected) - set(declared))
        extra = sorted(set(declared) - set(expected))
        wrong = sorted(name for name in set(expected) & set(declared) if expected[name] != declared[name])
        errors.append(
            f"release asset {checksum_path.name}: closure mismatch "
            f"missing={missing} extra={extra} wrong_digest={wrong}"
        )


def _validate_remote_release(
    assets: list[dict[str, Any]],
    binary_sections: dict[str, Any],
    errors: list[str],
) -> None:
    with tempfile.TemporaryDirectory() as raw:
        download_root = Path(raw)
        retained: dict[str, Path] = {}
        binary_names = set(binary_sections)
        for asset in assets:
            retain = (
                asset["name"] in binary_names
                or asset["kind"] in {"wheel", "checksum-manifest"}
            )
            destination = download_root / asset["name"] if retain else None
            _validate_remote_asset(asset, errors, destination)
            if destination is not None and destination.is_file():
                retained[asset["name"]] = destination

        asset_by_name = {asset["name"]: asset for asset in assets}
        binary_assets = {
            name: asset_by_name[name]
            for name in binary_names
            if name in asset_by_name and name in retained
        }
        for name, declaration in binary_sections.items():
            if name in retained and isinstance(declaration, dict):
                _verify_remote_binary(retained[name], declaration, errors)
        for asset in assets:
            if asset["kind"] == "wheel" and asset["name"] in retained:
                _verify_wheel_binary_closure(retained[asset["name"]], binary_assets, errors)
        checksum_assets = [asset for asset in assets if asset["kind"] == "checksum-manifest"]
        if len(checksum_assets) == 1 and checksum_assets[0]["name"] in retained:
            _verify_checksum_manifest(retained[checksum_assets[0]["name"]], assets, errors)


def validate_manifest(repo: Path, manifest_path: Path, check_remote: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read publication manifest {manifest_path}: {exc}"]

    label = manifest_path.relative_to(repo).as_posix()
    if not _is_tracked(repo, PurePosixPath(label)):
        errors.append(f"{label}: publication manifest is not tracked by Git")
    if manifest.get("format") != FORMAT:
        errors.append(f"{label}: format must be {FORMAT!r}")
    if manifest.get("publication_status") not in {"draft", "published"}:
        errors.append(f"{label}: publication_status must be 'draft' or 'published'")
    _repo_path(repo, manifest.get("guide"), f"{label}.guide", errors)

    repository = manifest.get("repository")
    if not isinstance(repository, dict):
        errors.append(f"{label}.repository must be an object")
        repository = {}
    source_commit = repository.get("source_commit")
    if not isinstance(source_commit, str) or not COMMIT_RE.fullmatch(source_commit):
        errors.append(f"{label}.repository.source_commit must be a full 40-character Git commit")
        source_commit = None
    elif subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{source_commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode != 0:
        errors.append(f"{label}.repository.source_commit is unavailable in this clone")
    scripts = repository.get("build_scripts")
    if not isinstance(scripts, list) or not scripts:
        errors.append(f"{label}.repository.build_scripts must be a non-empty list")
    else:
        for index, item in enumerate(scripts):
            item_label = f"{label}.repository.build_scripts[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{item_label} must bind path and sha256")
                continue
            value = item.get("path")
            expected = item.get("sha256")
            path = _repo_path(repo, value, f"{item_label}.path", errors)
            if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
                errors.append(f"{item_label}.sha256 must be a lowercase SHA-256 digest")
            if source_commit is not None and isinstance(value, str):
                blob = _git_blob(repo, source_commit, value)
                if blob is None:
                    errors.append(f"{item_label}: absent from source commit {source_commit}")
                elif isinstance(expected, str) and hashlib.sha256(blob).hexdigest() != expected:
                    errors.append(f"{item_label}: source-commit script digest mismatch")
            if path is not None and path.is_file():
                _validate_build_script(repo, path, errors)

    inputs = repository.get("immutable_inputs")
    if not isinstance(inputs, list) or not inputs:
        errors.append(f"{label}.repository.immutable_inputs must be a non-empty list")
    else:
        for index, item in enumerate(inputs):
            item_label = f"{label}.repository.immutable_inputs[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{item_label} must be an object")
                continue
            path = _repo_path(repo, item.get("path"), f"{item_label}.path", errors)
            input_path = item.get("path")
            expected = item.get("sha256")
            if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
                errors.append(f"{item_label}.sha256 must be a lowercase SHA-256 digest")
            elif path is not None and path.is_file() and _sha256(path) != expected:
                errors.append(f"{item_label}: repository artifact digest mismatch")
            if source_commit is not None and isinstance(input_path, str):
                blob = _git_blob(repo, source_commit, input_path)
                if blob is None:
                    errors.append(f"{item_label}: absent from source commit {source_commit}")
                elif isinstance(expected, str) and hashlib.sha256(blob).hexdigest() != expected:
                    errors.append(f"{item_label}: source-commit artifact digest mismatch")

    sources = manifest.get("source_repositories")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{label}.source_repositories must be a non-empty list")
    else:
        for index, source in enumerate(sources):
            source_label = f"{label}.source_repositories[{index}]"
            if not isinstance(source, dict):
                errors.append(f"{source_label} must be an object")
                continue
            if not isinstance(source.get("url"), str) or not source["url"].startswith("https://"):
                errors.append(f"{source_label}.url must be an HTTPS URL")
            if not isinstance(source.get("commit"), str) or not COMMIT_RE.fullmatch(source["commit"]):
                errors.append(f"{source_label}.commit must be a full 40-character Git commit")

    release = manifest.get("release")
    if not isinstance(release, dict):
        errors.append(f"{label}.release must be an object")
        release = {}
    if not isinstance(release.get("tag"), str) or not release["tag"]:
        errors.append(f"{label}.release.tag must be a non-empty immutable tag")
    if not isinstance(release.get("url"), str) or not release["url"].startswith("https://"):
        errors.append(f"{label}.release.url must be an HTTPS URL")
    assets = release.get("assets")
    found_kinds: set[str] = set()
    found_names: set[str] = set()
    valid_assets: list[dict[str, Any]] = []
    asset_kinds: dict[str, str] = {}
    if not isinstance(assets, list) or not assets:
        errors.append(f"{label}.release.assets must be a non-empty list")
    else:
        for index, asset in enumerate(assets):
            asset_label = f"{label}.release.assets[{index}]"
            if not isinstance(asset, dict):
                errors.append(f"{asset_label} must be an object")
                continue
            name = asset.get("name")
            kind = asset.get("kind")
            url = asset.get("url")
            digest = asset.get("sha256")
            size = asset.get("size")
            if not isinstance(name, str) or not name:
                errors.append(f"{asset_label}.name must be a non-empty string")
            elif name in found_names:
                errors.append(f"{asset_label}: duplicate asset name {name!r}")
            else:
                found_names.add(name)
            if not isinstance(kind, str) or not kind:
                errors.append(f"{asset_label}.kind must be a non-empty string")
            else:
                found_kinds.add(kind)
                if isinstance(name, str):
                    asset_kinds[name] = kind
            if not isinstance(url, str) or not url.startswith("https://"):
                errors.append(f"{asset_label}.url must be an HTTPS URL")
            elif isinstance(name, str) and unquote(PurePosixPath(urlparse(url).path).name) != name:
                errors.append(f"{asset_label}.url basename does not match asset name {name!r}")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(f"{asset_label}.sha256 must be a lowercase SHA-256 digest")
            if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                errors.append(f"{asset_label}.size must be a positive integer")
            if (
                isinstance(name, str)
                and PurePosixPath(name).name == name
                and isinstance(url, str)
                and url.startswith("https://")
                and isinstance(digest, str)
                and SHA256_RE.fullmatch(digest)
                and isinstance(size, int)
                and size > 0
                and isinstance(kind, str)
                and kind
            ):
                valid_assets.append(asset)
            elif isinstance(name, str) and PurePosixPath(name).name != name:
                errors.append(f"{asset_label}.name must not contain a path")

    binary_sections = manifest.get("binary_sections")
    if not isinstance(binary_sections, dict) or not binary_sections:
        errors.append(f"{label}.binary_sections must be a non-empty object")
    else:
        for asset_name, binary in binary_sections.items():
            binary_label = f"{label}.binary_sections[{asset_name!r}]"
            if asset_name not in found_names:
                errors.append(f"{binary_label}: binary is not a named release asset")
            elif asset_kinds.get(asset_name) not in CRITICAL_BINARY_KINDS:
                errors.append(f"{binary_label}: release asset is not a critical binary kind")
            if not isinstance(binary, dict):
                errors.append(f"{binary_label} must be an object")
                continue
            if binary.get("runpath") != "$ORIGIN":
                errors.append(f"{binary_label}.runpath must be '$ORIGIN'")
            sections = binary.get("sections")
            if not isinstance(sections, dict):
                errors.append(f"{binary_label}.sections must be an object")
                continue
            missing_sections = REQUIRED_BINARY_SECTIONS - set(sections)
            if missing_sections:
                errors.append(f"{binary_label}: missing section hashes {sorted(missing_sections)}")
            for section, digest in sections.items():
                if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                    errors.append(f"{binary_label}.sections[{section!r}] must be a SHA-256 digest")

    for asset_name, kind in asset_kinds.items():
        if kind in CRITICAL_BINARY_KINDS and (
            not isinstance(binary_sections, dict) or asset_name not in binary_sections
        ):
            errors.append(f"{label}: critical binary asset {asset_name!r} lacks section closure")

    toolchain = manifest.get("toolchain")
    if not isinstance(toolchain, dict):
        errors.append(f"{label}.toolchain must be an object")
        toolchain = {}
    for field in ("compiler", "python", "torch", "vllm", "vllm_xpu_kernels_source_version"):
        if not isinstance(toolchain.get(field), str) or not toolchain[field]:
            errors.append(f"{label}.toolchain.{field} must be a non-empty string")
    for field, expected_kind in (
        ("oneapi_inventory_asset", "toolchain-inventory"),
        ("runtime_inventory_asset", "runtime-inventory"),
    ):
        asset_name = toolchain.get(field)
        if not isinstance(asset_name, str) or asset_kinds.get(asset_name) != expected_kind:
            errors.append(
                f"{label}.toolchain.{field} must name a {expected_kind!r} release asset"
            )

    validation = manifest.get("validation")
    if not isinstance(validation, dict):
        errors.append(f"{label}.validation must be an object")
        validation = {}
    for field in ("clean_source_build", "runtime_smoke", "quality_gate"):
        if not isinstance(validation.get(field), bool):
            errors.append(f"{label}.validation.{field} must be boolean")
    build_log_asset = validation.get("build_log_asset")
    if not isinstance(build_log_asset, str) or asset_kinds.get(build_log_asset) != "build-log":
        errors.append(f"{label}.validation.build_log_asset must name the successful build-log asset")
    quality_evidence = validation.get("quality_evidence")
    if not isinstance(quality_evidence, list) or not quality_evidence:
        errors.append(f"{label}.validation.quality_evidence must be a non-empty list")
    else:
        for index, item in enumerate(quality_evidence):
            item_label = f"{label}.validation.quality_evidence[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{item_label} must bind path and sha256")
                continue
            path = _repo_path(repo, item.get("path"), f"{item_label}.path", errors)
            expected = item.get("sha256")
            if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
                errors.append(f"{item_label}.sha256 must be a lowercase SHA-256 digest")
            elif path is not None and path.is_file() and _sha256(path) != expected:
                errors.append(f"{item_label}: quality-evidence digest mismatch")

    if manifest.get("publication_status") == "published":
        missing_kinds = REQUIRED_RELEASE_KINDS - found_kinds
        if missing_kinds:
            errors.append(f"{label}: published recipe lacks release kinds {sorted(missing_kinds)}")
        if not all(validation.get(field) is True for field in (
            "clean_source_build", "runtime_smoke", "quality_gate"
        )):
            errors.append(f"{label}: published recipe requires all validation gates to pass")
        source_patch_assets = {
            (name, asset["sha256"])
            for asset in valid_assets
            if asset["kind"] == "source-patch"
            for name in [asset["name"]]
        }
        for item in inputs if isinstance(inputs, list) else []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                required = (PurePosixPath(item["path"]).name, item.get("sha256"))
                if required not in source_patch_assets:
                    errors.append(
                        f"{label}: immutable input {item['path']!r} lacks matching source-patch asset"
                    )
        remote_verified_at = release.get("remote_verified_at")
        if not isinstance(remote_verified_at, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", remote_verified_at
        ):
            errors.append(f"{label}: published release requires remote_verified_at in UTC")

    if check_remote and len(valid_assets) == len(assets or []):
        _validate_remote_release(
            valid_assets,
            binary_sections if isinstance(binary_sections, dict) else {},
            errors,
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="*", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-remote", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    manifests = args.manifests or sorted(repo.glob("repro/*/publication-manifest.json"))
    if not manifests:
        print("RECIPE PUBLICATION PASS manifests=0 remote=False")
        return 0
    errors: list[str] = []
    for value in manifests:
        path = value if value.is_absolute() else repo / value
        errors.extend(validate_manifest(repo, path.resolve(), args.check_remote))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"RECIPE PUBLICATION PASS manifests={len(manifests)} remote={args.check_remote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

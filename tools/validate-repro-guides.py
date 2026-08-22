#!/usr/bin/env python3
"""Validate reproduction-guide classification and public promotion policy."""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any
from urllib.parse import urlparse


FORMAT = "b70-reproduction-guide-catalog-v1"
CLASSIFICATIONS = {
    "starter-guide",
    "candidate-portable-repro",
    "lab-replay",
    "record-capsule",
    "research-status",
    "archived",
}
AUDIENCES = {"beginner", "intermediate", "expert", "researcher", "historical"}
COMPONENTS = {
    "platform_install",
    "model_download",
    "source_restore",
    "build",
    "launch",
    "validation",
    "patch_links",
    "hashes",
}
PACKAGE_FORMAT = "b70-model-package-v1"
PACKAGE_STATUSES = {"candidate", "starter", "preview"}
PACKAGE_COMMANDS = {"preflight", "launch", "health", "benchmark", "stop"}


class GuideAnchorParser(HTMLParser):
    """Collect anchor text and href without requiring third-party HTML packages."""

    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._text: list[str] = []
        self.anchors: list[tuple[str, str]] = []
        self.copy_markdown: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []
        elif tag == "button":
            copy_path = dict(attrs).get("data-copy-markdown")
            if copy_path is not None:
                self.copy_markdown.append(copy_path)

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.anchors.append((" ".join("".join(self._text).split()), self._href))
            self._href = None
            self._text = []


def _internal_path(value: str) -> PurePosixPath | None:
    """Return a repository-relative path for local or canonical GitHub links."""
    parsed = urlparse(value)
    if not parsed.scheme and not parsed.netloc:
        return PurePosixPath(parsed.path)
    if parsed.netloc == "github.com":
        prefix = "/steveseguin/b70-optimization-lab/blob/main/"
        if parsed.path.startswith(prefix):
            return PurePosixPath(parsed.path[len(prefix) :])
    return None


def validate(repo: Path, catalog_path: Path | None = None) -> tuple[list[str], Counter[str]]:
    errors: list[str] = []
    path = catalog_path or repo / "repro/guide-catalog.json"
    try:
        catalog: dict[str, Any] = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read catalog {path}: {exc}"], Counter()

    if catalog.get("format") != FORMAT:
        errors.append(f"catalog format must be {FORMAT!r}")

    guides = catalog.get("guides")
    if not isinstance(guides, list):
        return errors + ["catalog guides must be a list"], Counter()

    ids: set[str] = set()
    paths: set[str] = set()
    classifications: dict[str, str] = {}
    counts: Counter[str] = Counter()
    package_paths: set[str] = set()

    for index, entry in enumerate(guides):
        label = f"guides[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue

        guide_id = entry.get("id")
        guide = entry.get("guide")
        classification = entry.get("classification")
        audience = entry.get("audience")
        if not isinstance(guide_id, str) or not guide_id:
            errors.append(f"{label}.id must be a non-empty string")
        elif guide_id in ids:
            errors.append(f"duplicate guide id: {guide_id}")
        else:
            ids.add(guide_id)

        if not isinstance(guide, str) or not guide:
            errors.append(f"{label}.guide must be a non-empty string")
            continue
        if guide in paths:
            errors.append(f"duplicate guide path: {guide}")
        paths.add(guide)
        classifications[guide] = classification

        pure_guide = PurePosixPath(guide)
        if pure_guide.is_absolute() or ".." in pure_guide.parts:
            errors.append(f"{guide}: path must stay inside the repository")
        elif not (repo / pure_guide).is_file():
            errors.append(f"{guide}: guide does not exist")

        if classification not in CLASSIFICATIONS:
            errors.append(f"{guide}: unknown classification {classification!r}")
        else:
            counts[classification] += 1
        if audience not in AUDIENCES:
            errors.append(f"{guide}: unknown audience {audience!r}")
        if not isinstance(entry.get("clean_host_tested"), bool):
            errors.append(f"{guide}: clean_host_tested must be boolean")

        components = entry.get("components")
        if not isinstance(components, dict) or set(components) != COMPONENTS:
            errors.append(f"{guide}: components must contain exactly {sorted(COMPONENTS)}")
        elif any(type(value) is not bool for value in components.values()):
            errors.append(f"{guide}: every component value must be boolean")

        links = entry.get("dependency_links")
        if not isinstance(links, list):
            errors.append(f"{guide}: dependency_links must be a list")
        else:
            for link in links:
                if not isinstance(link, str):
                    errors.append(f"{guide}: dependency link must be a string")
                    continue
                internal = _internal_path(link)
                if internal is None:
                    errors.append(f"{guide}: dependency link must point inside this repository: {link}")
                elif internal.is_absolute() or ".." in internal.parts or not (repo / internal).exists():
                    errors.append(f"{guide}: dependency link does not resolve: {link}")

        missing = entry.get("missing")
        if not isinstance(missing, list) or any(not isinstance(item, str) or not item for item in missing):
            errors.append(f"{guide}: missing must be a list of non-empty strings")
        elif classification != "starter-guide" and not missing:
            errors.append(f"{guide}: non-starter guides must state at least one missing gate")

        if classification == "starter-guide":
            if entry.get("clean_host_tested") is not True:
                errors.append(f"{guide}: starter-guide requires a clean-host replay")
            if isinstance(components, dict) and not all(components.values()):
                errors.append(f"{guide}: starter-guide has incomplete dependency closure")
            if missing:
                errors.append(f"{guide}: starter-guide cannot retain missing gates")
            if audience != "beginner":
                errors.append(f"{guide}: starter-guide audience must be beginner")

        package = entry.get("package")
        if package is not None:
            if not isinstance(package, str) or not package:
                errors.append(f"{guide}: package must be a non-empty repository-relative path")
            else:
                package_paths.add(package)
                errors.extend(_validate_package(repo, package, entry))

    discovered = {
        item.relative_to(repo).as_posix()
        for item in (repo / "repro").glob("*/README.md")
        if item.is_file()
    }
    for missing_path in sorted(discovered - paths):
        errors.append(f"uncatalogued reproduction guide: {missing_path}")
    for stale_path in sorted(paths - discovered):
        errors.append(f"catalog path is not a repro/*/README.md guide: {stale_path}")

    discovered_packages = {
        item.relative_to(repo).as_posix()
        for item in (repo / "packages").glob("*/package.json")
        if item.is_file()
    }
    for missing_path in sorted(discovered_packages - package_paths):
        errors.append(f"unregistered model package: {missing_path}")
    for stale_path in sorted(package_paths - discovered_packages):
        errors.append(f"registered model package does not exist: {stale_path}")

    index_path = repo / "index.html"
    try:
        parser = GuideAnchorParser()
        parser.feed(index_path.read_text())
        for text, href in parser.anchors:
            if text.casefold() != "read guide":
                continue
            internal = _internal_path(href)
            key = internal.as_posix() if internal is not None else None
            if key is None or classifications.get(key) != "starter-guide":
                errors.append(
                    f"index.html promotes {href!r} as 'Read guide', but it is not a certified starter-guide"
                )
        for copy_path in parser.copy_markdown:
            internal = _internal_path(copy_path)
            if internal is None or internal.is_absolute() or ".." in internal.parts:
                errors.append(f"index.html Copy Markdown target is not repository-relative: {copy_path}")
            elif not (repo / internal).is_file():
                errors.append(f"index.html Copy Markdown target does not exist: {copy_path}")
    except OSError as exc:
        errors.append(f"cannot read index.html: {exc}")

    return errors, counts


def _validate_package(repo: Path, package_path: str, guide_entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pure = PurePosixPath(package_path)
    label = package_path
    if pure.is_absolute() or ".." in pure.parts:
        return [f"{label}: package path must stay inside the repository"]
    path = repo / pure
    try:
        package: dict[str, Any] = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read package {label}: {exc}"]

    if package.get("format") != PACKAGE_FORMAT:
        errors.append(f"{label}: format must be {PACKAGE_FORMAT!r}")
    if package.get("id") != guide_entry.get("id"):
        errors.append(f"{label}: id must match its guide-catalog entry")
    if package.get("guide") != guide_entry.get("guide"):
        errors.append(f"{label}: guide must match its guide-catalog entry")
    if package.get("audience") != guide_entry.get("audience"):
        errors.append(f"{label}: audience must match its guide-catalog entry")
    if package.get("clean_host_tested") != guide_entry.get("clean_host_tested"):
        errors.append(f"{label}: clean_host_tested must match its guide-catalog entry")

    status = package.get("status")
    if status not in PACKAGE_STATUSES:
        errors.append(f"{label}: unknown package status {status!r}")
    guide_class = guide_entry.get("classification")
    if status == "starter" and guide_class != "starter-guide":
        errors.append(f"{label}: starter package requires starter-guide certification")
    if status == "starter" and package.get("clean_host_tested") is not True:
        errors.append(f"{label}: starter package requires clean_host_tested=true")

    hardware = package.get("hardware")
    if not isinstance(hardware, dict) or not isinstance(hardware.get("cards"), int) or hardware["cards"] < 1:
        errors.append(f"{label}: hardware.cards must be a positive integer")

    model = package.get("model")
    if not isinstance(model, dict):
        errors.append(f"{label}: model must be an object")
    else:
        revision = model.get("revision")
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            errors.append(f"{label}: model revision must be an immutable 40-character commit")
        errors.extend(_validate_internal_dependency(repo, label, model.get("manifest")))

    runtime = package.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("kind") not in {"container", "native"}:
        errors.append(f"{label}: runtime.kind must be container or native")
    elif runtime["kind"] == "container":
        image = runtime.get("image")
        if not isinstance(image, str) or re.fullmatch(r".+@sha256:[0-9a-f]{64}", image) is None:
            errors.append(f"{label}: container image must be pinned by sha256 digest")

    patches = package.get("project_patches")
    if not isinstance(patches, dict) or type(patches.get("required")) is not bool:
        errors.append(f"{label}: project_patches.required must be boolean")
    elif not isinstance(patches.get("items"), list):
        errors.append(f"{label}: project_patches.items must be a list")
    elif patches["required"] and not patches["items"]:
        errors.append(f"{label}: required project patches cannot have an empty item list")
    elif not patches["required"] and patches["items"]:
        errors.append(f"{label}: patch items exist while project_patches.required is false")
    else:
        for item in patches["items"]:
            errors.extend(_validate_internal_dependency(repo, label, item))

    commands = package.get("commands")
    if not isinstance(commands, dict) or set(commands) != PACKAGE_COMMANDS:
        errors.append(f"{label}: commands must contain exactly {sorted(PACKAGE_COMMANDS)}")
    elif any(not isinstance(value, str) or not value.strip() for value in commands.values()):
        errors.append(f"{label}: package commands must be non-empty strings")

    dependencies = package.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        errors.append(f"{label}: dependencies must be a non-empty list")
    else:
        for dependency in dependencies:
            errors.extend(_validate_internal_dependency(repo, label, dependency))

    missing = package.get("missing")
    if status == "starter" and missing:
        errors.append(f"{label}: starter package cannot retain missing gates")
    elif status != "starter" and (
        not isinstance(missing, list)
        or not missing
        or any(not isinstance(item, str) or not item for item in missing)
    ):
        errors.append(f"{label}: non-starter package must state missing gates")
    return errors


def _validate_internal_dependency(repo: Path, owner: str, value: object) -> list[str]:
    if not isinstance(value, str):
        return [f"{owner}: dependency must be a repository-relative string"]
    internal = _internal_path(value)
    if internal is None or internal.is_absolute() or ".." in internal.parts:
        return [f"{owner}: dependency must point inside this repository: {value}"]
    if not (repo / internal).exists():
        return [f"{owner}: dependency does not resolve: {value}"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args(argv)
    errors, counts = validate(args.repo.resolve(), args.catalog)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"guide catalog validation failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    summary = ", ".join(f"{name}={counts[name]}" for name in sorted(counts))
    print(f"guide catalog valid: {sum(counts.values())} guides ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Keep the root README's public package headlines synced to package manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CATALOG = ROOT / "packages" / "catalog.json"
START = "<!-- BEGIN GENERATED PUBLIC PACKAGE HEADLINES -->"
END = "<!-- END GENERATED PUBLIC PACKAGE HEADLINES -->"


def format_value(value: float) -> str:
    return f"{value:,.6f}".rstrip("0").rstrip(".")


def missing_headline_label(library: dict) -> str:
    status = str(library.get("benchmark_status", ""))
    return "strict headline withheld" if "withheld" in status.lower() else "strict headline pending"


def render() -> str:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    packages = sorted(
        catalog["packages"],
        key=lambda item: (
            (item["library"].get("featured_metric") or {}).get("value") is not None,
            float((item["library"].get("featured_metric") or {}).get("value") or 0),
        ),
        reverse=True,
    )
    lines = [
        START,
        "| Model and deployment | Package status | Measured headline | Exact guide |",
        "| --- | --- | ---: | --- |",
    ]
    for package in packages:
        library = package["library"]
        metric = library.get("featured_metric")
        hardware = package["hardware"]
        clean_host = "clean-host tested" if package["clean_host_tested"] else "clean-host replay pending"
        deployment = (
            f"{hardware['cards']}&times; B70 · {library['quantization']} · "
            f"{library['runtime_label']}"
        )
        detail = f"models/{package['id']}.html"
        measured = (
            f"**`{format_value(float(metric['value']))} {metric['unit']}`**<br>"
            f"{metric['label']}"
            if isinstance(metric, dict)
            else f"**{missing_headline_label(library)}**<br>{library['benchmark_status']}"
        )
        lines.append(
            f"| **[{package['name']}]({detail})**<br>{deployment} | "
            f"`{package['status']}` · {clean_host} | "
            f"{measured} | [reproduction guide]({package['guide']}) |"
        )
    lines.append(END)
    return "\n".join(lines)


def update(check: bool) -> int:
    current = README.read_text(encoding="utf-8")
    if START not in current or END not in current:
        raise SystemExit("README.md is missing generated package-headline markers")
    before, remainder = current.split(START, 1)
    _, after = remainder.split(END, 1)
    expected = before + render() + after
    if current == expected:
        print("README public package headlines current")
        return 0
    if check:
        print("README public package headlines are stale")
        return 1
    README.write_text(expected, encoding="utf-8", newline="\n")
    print("updated README public package headlines")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    return update(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
